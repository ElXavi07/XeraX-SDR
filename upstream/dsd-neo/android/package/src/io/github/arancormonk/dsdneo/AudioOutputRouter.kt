// SPDX-License-Identifier: GPL-3.0-or-later
package io.github.arancormonk.dsdneo

import android.content.Context
import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.os.Handler
import android.os.Looper
import org.json.JSONArray
import org.json.JSONObject

/** Media-output preference shared by Qt and the foreground service. Device
 * callbacks keep unplug recovery working even while the UI is in the background. */
object AudioOutputRouter {
    private var app: Context? = null
    private var manager: AudioManager? = null
    private var selection = "speaker"
    private var note = ""
    private var appliedId = -1
    private val callback = object : AudioDeviceCallback() {
        override fun onAudioDevicesAdded(devices: Array<out AudioDeviceInfo>) { refresh() }
        override fun onAudioDevicesRemoved(devices: Array<out AudioDeviceInfo>) { refresh() }
    }

    @JvmStatic @Synchronized
    fun initialize(context: Context) {
        if (manager != null) return
        val application = context.applicationContext
        val audio = application.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        app = application
        manager = audio
        selection = application.getSharedPreferences("audio-routing", Context.MODE_PRIVATE)
            .getString("route", "speaker").let { if (it == "default") "default" else "speaker" }
        audio.registerAudioDeviceCallback(callback, Handler(Looper.getMainLooper()))
        refresh()
    }

    private fun outputs(): List<AudioDeviceInfo> =
        manager?.getDevices(AudioManager.GET_DEVICES_OUTPUTS)?.filter { it.isSink } ?: emptyList()

    private fun speaker(devices: List<AudioDeviceInfo>): AudioDeviceInfo? =
        devices.firstOrNull { it.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER }

    private fun selectedId(devices: List<AudioDeviceInfo>): Int = when (selection) {
        "default" -> 0
        "speaker" -> speaker(devices)?.id ?: 0
        else -> selection.removePrefix("device:").toIntOrNull() ?: 0
    }

    @Synchronized private fun refresh() {
        val devices = outputs()
        if (selection.startsWith("device:") && devices.none { "device:${it.id}" == selection }) {
            selection = "speaker"
            note = "Selected output disconnected; requesting phone speaker."
        }
        val id = selectedId(devices)
        if (id != appliedId && DsdNative.nativeSetAudioOutputDevice(id) == 0) { appliedId = id; ReceiverWorkers.routeAudio(id) }
    }

    @JvmStatic @Synchronized
    fun select(context: Context, key: String): Boolean {
        initialize(context)
        val devices = outputs()
        if (key != "default" && key != "speaker" && devices.none { "device:${it.id}" == key }) return false
        if (key == "speaker" && speaker(devices) == null) return false
        selection = key
        appliedId = -1 // Selecting the same device explicitly retries an OS-overridden route.
        note = ""
        // Android IDs are transient. Persist only stable choices; external
        // devices must be chosen again after a process restart.
        app!!.getSharedPreferences("audio-routing", Context.MODE_PRIVATE).edit()
            .putString("route", if (key == "default") "default" else "speaker").apply()
        refresh()
        return true
    }

    @JvmStatic @Synchronized
    fun preferredDevice(context: Context): AudioDeviceInfo? {
        initialize(context)
        val devices = outputs()
        val id = selectedId(devices)
        return devices.firstOrNull { it.id == id }
    }

    private fun label(device: AudioDeviceInfo): String {
        val type = when (device.type) {
            AudioDeviceInfo.TYPE_BUILTIN_SPEAKER -> "Phone speaker"
            AudioDeviceInfo.TYPE_BUILTIN_EARPIECE -> "Phone earpiece"
            AudioDeviceInfo.TYPE_WIRED_HEADPHONES, AudioDeviceInfo.TYPE_WIRED_HEADSET -> "Wired headphones"
            AudioDeviceInfo.TYPE_BLUETOOTH_A2DP -> "Bluetooth audio"
            AudioDeviceInfo.TYPE_BLUETOOTH_SCO -> "Bluetooth call audio"
            AudioDeviceInfo.TYPE_BLE_HEADSET, AudioDeviceInfo.TYPE_BLE_SPEAKER -> "Bluetooth LE audio"
            AudioDeviceInfo.TYPE_USB_DEVICE, AudioDeviceInfo.TYPE_USB_HEADSET, AudioDeviceInfo.TYPE_USB_ACCESSORY -> "USB audio"
            AudioDeviceInfo.TYPE_HDMI, AudioDeviceInfo.TYPE_HDMI_ARC, AudioDeviceInfo.TYPE_HDMI_EARC -> "HDMI audio"
            else -> "Audio output"
        }
        val product = device.productName?.toString()?.trim().orEmpty()
        return if (device.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER || device.type == AudioDeviceInfo.TYPE_BUILTIN_EARPIECE || product.isEmpty()) type else "$type · $product"
    }

    @JvmStatic @Synchronized
    fun snapshot(context: Context): String {
        initialize(context)
        val devices = outputs()
        val choices = JSONArray().put(JSONObject().put("key", "default").put("label", "System default"))
        speaker(devices)?.let { choices.put(JSONObject().put("key", "speaker").put("label", "Phone speaker")) }
        for (device in devices.filter { it.type != AudioDeviceInfo.TYPE_BUILTIN_SPEAKER }.sortedBy { it.id }) {
            choices.put(JSONObject().put("key", "device:${device.id}").put("label", label(device)))
        }
        return JSONObject().put("choices", choices).put("selected", selection)
            .put("requestedId", selectedId(devices)).put("note", note).toString()
    }
}
