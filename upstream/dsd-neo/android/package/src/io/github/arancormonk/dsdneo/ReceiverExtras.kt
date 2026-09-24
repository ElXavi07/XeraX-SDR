// SPDX-License-Identifier: GPL-3.0-or-later
package io.github.arancormonk.dsdneo
import android.content.Context
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.media.AudioManager
import android.media.AudioFocusRequest
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.os.BatteryManager
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import org.json.JSONObject
object ReceiverExtras {
    @Volatile private var workerAudio=false
    @JvmStatic fun setWorkerAudio(enabled:Boolean) { workerAudio=enabled; DsdNative.nativeSuppressLiveAudio(workerAudio || focusLost || playing || testing); ReceiverWorkers.suspendAudio(focusLost || playing || testing) }
    private var app: Context? = null
    private var player: MediaPlayer? = null
    private var replayFile: java.io.File? = null
    private val focusLease = AudioFocusLease()
    private val focusLost get() = focusLease.blocked
    @Volatile private var testing = false
    @Volatile private var testStatus = ""
    @Volatile private var spanish = java.util.Locale.getDefault().language == "es"
    @JvmStatic fun setLanguage(language: String) {
        spanish = language == "es"
        app?.getSharedPreferences("receiver-ui", Context.MODE_PRIVATE)?.edit()?.putString("language", language)?.apply()
    }
    fun text(english: String, translated: String): String = if (spanish) translated else english
    @Volatile private var playing = false
    @Volatile private var playbackError = ""
    private var focus: AudioFocusRequest? = null
    private val lastAlerts = mutableMapOf<String, Long>()
    @JvmStatic fun configureAlerts(context: Context, text: String): Boolean {
        val rules = text.split(',', ' ', '\n', ';').filter { it.isNotBlank() }
        if (rules.size > 64 || rules.any { !Regex("(tg|rid):[1-9][0-9]{0,7}").matches(it) || it.substringAfter(':').toLong() > 16777215 }) return false
        context.getSharedPreferences("receiver-alerts", Context.MODE_PRIVATE).edit().putString("rules", rules.distinct().joinToString(",")).apply()
        return true
    }
    @JvmStatic fun alertRules(context: Context): String = context.getSharedPreferences("receiver-alerts", Context.MODE_PRIVATE).getString("rules", "") ?: ""
    fun observe(context: Context, status: DecoderStatus?) {
        if (!DecoderService.audioSessionActive() && player == null && !testing && focus != null) {
            Handler(Looper.getMainLooper()).post { if (!DecoderService.audioSessionActive() && player == null && !testing) releasePlayer() }
        }
        if (status == null) return
        val rules = alertRules(context).split(',').toSet()
        if (rules.isEmpty() || rules == setOf("")) return
        val ids = DsdNative.nativeCallIdentities() ?: return
        val now = android.os.SystemClock.elapsedRealtime()
        lastAlerts.entries.removeAll { now - it.value > 60000 }
        for (slot in 0..1) {
            if (ids.size < (slot + 1) * 3 || ids[slot * 3] != 2L) continue
            val matches = listOf("tg:${ids[slot * 3 + 1]}", "rid:${ids[slot * 3 + 2]}").filter { it in rules }
            if (matches.isEmpty()) continue
            val key = status.protocol + ":" + matches.joinToString()
            if (now - (lastAlerts[key] ?: -60000) < 30000) continue
            lastAlerts[key] = now
            val manager = context.getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(NotificationChannel("receiver-alerts", text("Radio activity alerts", "Avisos de actividad de radio"), NotificationManager.IMPORTANCE_DEFAULT))
            val open = PendingIntent.getActivity(context, 90, Intent(context, DsdNeoActivity::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val text = matches.joinToString(" · ") + " · " + status.protocol
            val note = Notification.Builder(context, "receiver-alerts").setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(text("XeraX SDR activity", "Actividad de XeraX SDR")).setContentText(text).setContentIntent(open).setAutoCancel(true).build()
            try { manager.notify(900 + slot, note) } catch (_: SecurityException) { /* OS notification permission controls alerts. */ }
        }
    }
    @JvmStatic fun initialize(context: Context) {
        app = context.applicationContext
        spanish = context.getSharedPreferences("receiver-ui", Context.MODE_PRIVATE).getString("language", java.util.Locale.getDefault().language) == "es"
    }
    private fun requestFocus(context: Context, force: Boolean = false): Boolean {
        val audio = context.getSystemService(AudioManager::class.java)
        if (!force && focus != null && focusLease.granted) return true
        val token = focusLease.begin()
        focus?.let { audio.abandonAudioFocusRequest(it) }
        val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
            .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            .setWillPauseWhenDucked(true)
            .setAcceptsDelayedFocusGain(true)
            .setOnAudioFocusChangeListener(listener@{ change ->
                if (!focusLease.change(token, change == AudioManager.AUDIOFOCUS_GAIN)) return@listener
                if (focusLost) { DsdNative.nativeCancelAudioTest(); releasePlayer() }
                DsdNative.nativeHostDiagnostic("Audio focus changed: $change")
                DsdNative.nativeSuppressLiveAudio(workerAudio || focusLost || playing || testing); ReceiverWorkers.suspendAudio(focusLost || playing || testing)
            }, Handler(Looper.getMainLooper())).build()
        focus = request
        val result = audio.requestAudioFocus(request)
        focusLease.change(token, result == AudioManager.AUDIOFOCUS_REQUEST_GRANTED)
        DsdNative.nativeHostDiagnostic("Audio focus request result: $result")
        DsdNative.nativeSuppressLiveAudio(workerAudio || focusLost || playing || testing); ReceiverWorkers.suspendAudio(focusLost || playing || testing)
        return !focusLost
    }
    @JvmStatic fun resumeLive(context: Context) {
        initialize(context)
        Handler(Looper.getMainLooper()).post { releasePlayer(); requestFocus(context) }
    }
    @JvmStatic fun restoreAudio(context: Context) {
        initialize(context)
        Handler(Looper.getMainLooper()).post {
            DsdNative.nativeCancelAudioTest()
            ReceiverWorkers.listen(-1)
            workerAudio = false
            releasePlayer()
            AudioOutputRouter.select(context, "speaker")
            playbackError = ""
            requestFocus(context, true)
        }
    }
    @JvmStatic fun testAudio(context: Context) {
        initialize(context)
        Handler(Looper.getMainLooper()).post {
            if (testing) return@post
            releasePlayer()
            playbackError = ""
            if (!requestFocus(context, true)) {
                testStatus = text("Audio focus unavailable. Close other audio apps and retry.", "Audio ocupado. Cierra otras aplicaciones de audio e intenta otra vez.")
                return@post
            }
            testing = true
            testStatus = text("Playing two test tones...", "Reproduciendo dos tonos de prueba...")
            DsdNative.nativeSuppressLiveAudio(true)
            ReceiverWorkers.suspendAudio(true)
            val testToken = DsdNative.nativeAudioTestToken()
            Thread({
                val result = try { DsdNative.nativeTestAudioOutput(testToken) } catch (_: Exception) { -1 }
                Handler(Looper.getMainLooper()).post {
                    testing = false
                    testStatus = when (result) {
                        0 -> text("Two tones sent to the output. Audible sound still needs your confirmation.", "Dos tonos enviados a la salida. Confirma si los escuchaste.")
                        -2 -> text("Audio test interrupted by another app.", "Prueba interrumpida por otra aplicación.")
                        else -> text("Android did not accept the test audio. Retry the output or select System default.", "Android no aceptó el audio. Reintenta o selecciona Salida del sistema.")
                    }
                    DsdNative.nativeHostDiagnostic("Audio output test result: $result")
                    releasePlayer()
                }
            }, "xerax-audio-test").start()
        }
    }
    @JvmStatic fun health(context: Context): String {
        initialize(context)
        val power = context.getSystemService(PowerManager::class.java)
        val battery = context.getSystemService(BatteryManager::class.java)
        val usb = UsbSourceManager.inventory(context)
        return JSONObject().put("usb", usb).put("hackrfActive", usb.getBoolean("hackrfActive")).put("thermal", power.currentThermalStatus)
            .put("powerSave", power.isPowerSaveMode)
            .put("battery", battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY))
            .put("focusLost", focusLost).put("replaying", playing)
            .put("testingAudio", testing).put("audioTestStatus", testStatus).put("workerAudio", workerAudio).put("playbackError", playbackError)
            .put("mediaVolume", context.getSystemService(AudioManager::class.java).getStreamVolume(AudioManager.STREAM_MUSIC)).toString()
    }
    @JvmStatic fun play(context: Context, path: String): Boolean {
        initialize(context)
        Handler(Looper.getMainLooper()).post {
            releasePlayer()
            playbackError = ""
            replayFile = java.io.File(path)
            try {
                val next = MediaPlayer()
                player = next
                next.setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                next.setPreferredDevice(AudioOutputRouter.preferredDevice(context))
                next.setDataSource(path)
                next.setOnPreparedListener {
                    if (requestFocus(context)) {
                        DsdNative.nativeSuppressLiveAudio(true)
                        playing = true
                        ReceiverWorkers.suspendAudio(true)
                        it.start()
                    } else { playbackError = text("Audio focus unavailable", "Audio ocupado por otra aplicación"); releasePlayer() }
                }
                next.setOnCompletionListener { stopPlayback() }
                next.setOnErrorListener { _, _, _ -> playbackError = text("Playback failed", "Error de reproducción"); stopPlayback(); true }
                next.prepareAsync()
            } catch (_: Exception) { playbackError = text("Playback failed", "Error de reproducción"); releasePlayer() }
        }
        return true
    }
    private fun releasePlayer() {
        playing = false
        DsdNative.nativeSuppressLiveAudio(workerAudio || focusLost || testing)
        ReceiverWorkers.suspendAudio(focusLost || testing)
        player?.release(); player = null
        replayFile?.let { if (it.name.startsWith("xerax-replay-") && it.parentFile == app?.cacheDir) it.delete() }
        replayFile = null
        if (!DecoderService.audioSessionActive() && !testing) {
            focusLease.abandon()
            focus?.let { app?.getSystemService(AudioManager::class.java)?.abandonAudioFocusRequest(it) }; focus = null
        }
    }
    @JvmStatic fun stopPlayback() {
        Handler(Looper.getMainLooper()).post {
            releasePlayer()
        }
    }
}
