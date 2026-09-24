// SPDX-License-Identifier: GPL-3.0-or-later
package io.github.arancormonk.dsdneo

import android.app.*
import android.content.*
import android.content.pm.ServiceInfo
import android.hardware.usb.*
import android.os.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** Private Messenger IPC: each bound service owns exactly one engine in a separate process. */
object ReceiverWorkers {
    const val START=1; const val STOP=2; const val STATUS=3; const val AUDIO=4; const val TUNE=5
    private val handler=Handler(Looper.getMainLooper())
    private data class Lane(var remote: Messenger?=null, var connection: ServiceConnection?=null,
        var state: JSONObject=JSONObject().put("state","idle"), @Volatile var wanted: Boolean=false, @Volatile var request:Long=0)
    private val lanes=Array(4){Lane()}
    private val requestIds=java.util.concurrent.atomic.AtomicLong()
    private var app: Context?=null
    @Volatile private var audible=-1
    @Volatile private var audioBlocked=false
    @Volatile private var outputDevice=0
    private var thermal=false
    @Volatile private var site=false
    @Volatile private var siteAuto=true
    private var siteMuted=false
    private val selector=SiteAudioSelector(4)
    @JvmStatic fun prepareSite(enabled:Boolean) { handler.post {
        site=enabled; siteAuto=true; siteMuted=false; selector.reset(); audible=-1
        ReceiverExtras.setWorkerAudio(site); handler.removeCallbacks(sitePump)
        if(site) handler.postDelayed(sitePump,250)
    } }
    @JvmStatic fun autoSiteAudio() { handler.post { siteAuto=true } }
    @JvmStatic fun stopAll() { handler.post {
        site=false; handler.removeCallbacks(sitePump)
        dualArgs=null; pendingGrant=null; handler.removeCallbacks(dualPump); DsdNative.nativeDual(false)
        for(i in lanes.indices) { lanes[i].wanted=false; send(i,STOP) }
        audible=-1; ReceiverExtras.setWorkerAudio(false); updateAudio()
    } }
    private val sitePump=object:Runnable { override fun run() {
        if(!site) return
        val muted=DsdNative.nativeAudioProgress().getOrNull(3)==1L
        if(muted!=siteMuted) { siteMuted=muted; updateAudio() }
        val now=SystemClock.elapsedRealtime()
        val snapshot=synchronized(lanes) { lanes.map { JSONObject(it.state.toString()) } }
        val chosen=selector.choose(now, snapshot.map { it.optLong("nonzeroFrames") },
            snapshot.map { it.optString("state")=="running" && it.optBoolean("active") && now-it.optLong("receivedAt")<1500 },audible)
        if(siteAuto && chosen!=audible) { audible=chosen; updateAudio() }
        for(i in lanes.indices) send(i,STATUS)
        handler.postDelayed(this,250)
    } }

    @Volatile private var dualArgs:Array<String>?=null
    private var dualDevice=""
    private var grantSequence=0L
    private var voiceFrequency=0L
    private var voiceTarget=0L
    private var voiceAt=0L
    private var pendingGrant:LongArray?=null
    private var pendingAt=0L
    private var seenGrant=0L
    private var seenAt=0L
    private var voiceContext:List<Long> = emptyList()
    private var tuneLatency=0L
    @JvmStatic fun requestDevice(context:Context,id:String):Boolean {
        val manager=context.getSystemService(UsbManager::class.java)
        val device=manager.deviceList[id] ?: return false
        if(id==UsbSourceManager.activeDeviceName()) return false
        if(manager.hasPermission(device)) return true
        manager.requestPermission(device,PendingIntent.getBroadcast(context,213,Intent(context.packageName+".WORKER_USB").setPackage(context.packageName),PendingIntent.FLAG_IMMUTABLE))
        return true
    }
    @JvmStatic fun armDual(context:Context,arguments:String,device:String):Boolean {
        if(device.isEmpty() || device==UsbSourceManager.activeDeviceName()) return false
        val manager=context.getSystemService(UsbManager::class.java)
        if(manager.deviceList[device]?.let { manager.hasPermission(it) }!=true) return false
        val args=try { JSONArray(arguments).let { a -> Array(a.length()){a.getString(it)} } } catch(_:Exception) { return false }
        if(!start(context,0,arguments,device)) return false
        handler.post {
            dualArgs=args; dualDevice=device; grantSequence=0; voiceFrequency=0; voiceTarget=0; voiceAt=0
            pendingGrant=null; voiceContext=emptyList(); seenGrant=0; tuneLatency=0
            DsdNative.nativeDual(true); handler.removeCallbacks(dualPump); handler.post(dualPump)
        }
        return true
    }
    @JvmStatic fun disarmDual() { handler.post { dualArgs=null; pendingGrant=null; DsdNative.nativeDual(false); handler.removeCallbacks(dualPump); stop(0); listen(-1) } }
    private val dualPump=object:Runnable { override fun run() {
        val base=dualArgs ?: return
        if(!DsdNative.nativeIsRunning() || thermal) { disarmDual(); return }
        val now=SystemClock.elapsedRealtime()
        val status=synchronized(lanes) { JSONObject(lanes[0].state.toString()) }
        if(status.optString("state") in listOf("failed","stopped","complete")) { disarmDual(); return }
        pendingGrant?.let { pending ->
            if(status.optLong("voiceSequence")==pending[0] && status.optInt("voiceResult")==1) {
                voiceFrequency=pending[1]; voiceTarget=pending[5]; voiceAt=now
                voiceContext=pending.slice(1..5)+pending.slice(7..8)
                tuneLatency=now-pendingAt; pendingGrant=null
            } else if((status.optLong("voiceSequence")==pending[0] && status.optInt("voiceResult")==-1) || now-pendingAt>5000) {
                disarmDual(); return
            }
        }
        val grant=DsdNative.nativeDualGrant()
        if(grant!=null && grant.size==10 && grant[0]!=grantSequence) {
            if(seenGrant!=grant[0]) { seenGrant=grant[0]; seenAt=now }
            val current=DecoderStatus.parse(status.optString("record"))
            val occupied=current?.slots?.any { it.state==DecoderStatus.LINE_ACTIVE }==true
            val context=grant.slice(1..5)+grant.slice(7..8)
            if(context==voiceContext) grantSequence=grant[0]
            else if(pendingGrant==null && now-seenAt<=1500 && status.optString("state")=="running"
                && (!occupied || now-voiceAt>30000) && now-voiceAt>=200) {
                // One atomic decoder-thread command, preserving USB, audio and supplied keys.
                pendingGrant=grant.copyOf(); pendingAt=now; grantSequence=grant[0]
                send(0,TUNE,Bundle().apply { putLongArray("grant",grant); putInt("modulation",if(base.contains("-mq")) 1 else 0); putLong("request",lanes[0].request) })
            }
        }
        send(0,STATUS); handler.postDelayed(this,150)
    } }
    private val replies=Messenger(Handler(Looper.getMainLooper()) { msg ->
        val index=msg.arg1
        if(index in 0..3) try {
            val next=JSONObject(msg.data.getString("status") ?: "{}")
            if(next.optLong("request")!=lanes[index].request) return@Handler true
            next.put("receivedAt",SystemClock.elapsedRealtime())
            synchronized(lanes) { lanes[index].state=next }
            if(next.optString("state") in listOf("complete","failed","stopped")) {
                synchronized(lanes) { lanes[index].wanted=false }
                if(audible==index) { audible=-1; ReceiverExtras.setWorkerAudio(site); updateAudio() }
                if(index==0 && dualArgs!=null) disarmDual()
                // Keep final diagnostics briefly for the lab, then release the
                // bound process. A new run cancels cleanup through wanted.
                val oldRemote=lanes[index].remote; val oldRequest=lanes[index].request
                handler.postDelayed({
                    if(!lanes[index].wanted && lanes[index].request==oldRequest && lanes[index].remote===oldRemote) {
                        lanes[index].connection?.let { try { app?.unbindService(it) } catch(_:Exception) { } }
                        lanes[index].connection=null; lanes[index].remote=null
                    }
                },5000)
            }
        } catch (_:Exception) { }
        true
    })
    private fun type(lane: Int): Class<out Service> = when(lane) {
        0 -> ReceiverWorkerOne::class.java; 1 -> ReceiverWorkerTwo::class.java
        2 -> ReceiverWorkerThree::class.java; else -> ReceiverWorkerFour::class.java
    }
    private fun send(lane:Int, what:Int, data:Bundle=Bundle()) {
        try { lanes[lane].remote?.send(Message.obtain(null,what,lane,0).apply { this.data=data; replyTo=replies }) }
        catch (_:Exception) { synchronized(lanes) { lanes[lane].state=JSONObject().put("state","failed").put("error","Worker disconnected") }; lanes[lane].wanted=false }
    }
    @JvmStatic fun start(context:Context,lane:Int,arguments:String,device:String):Boolean {
        if(lane !in 0..3) return false
        if(device.isNotEmpty() && device==UsbSourceManager.activeDeviceName()) return false
        val args=try { JSONArray(arguments).let { a -> Array(a.length()){a.getString(it)} } } catch (_:Exception) { return false }
        if(args.size !in 2..256 || args.any { it.length>4096 }) return false
        app=context.applicationContext
        val request=requestIds.incrementAndGet()
        synchronized(lanes) { if(lanes[lane].wanted) return false; lanes[lane].wanted=true; lanes[lane].request=request; lanes[lane].state=JSONObject().put("state","starting") }
        handler.post {
            if(thermal) { lanes[lane].wanted=false; lanes[lane].state=JSONObject().put("state","failed").put("error","Phone is too warm; retry after cooling"); return@post }
            val payload=Bundle().apply { putLong("request",request); putStringArray("args",args); putString("device",device); putBoolean("audible",audible==lane && !audioBlocked); putInt("outputDevice",outputDevice) }
            if(lanes[lane].remote!=null) {
                try { context.applicationContext.startForegroundService(Intent(context,type(lane))); send(lane,START,payload) }
                catch(_:Exception) { synchronized(lanes) { lanes[lane].wanted=false; lanes[lane].state=JSONObject().put("state","failed").put("error","Could not start receiver service") } }
                return@post
            }
            val connection=object:ServiceConnection {
                override fun onServiceConnected(name:ComponentName,binder:IBinder) {
                    if(lanes[lane].request!=request) { try { context.applicationContext.unbindService(this) } catch(_:Exception) { }; return }
                    lanes[lane].remote=Messenger(binder)
                    payload.putBoolean("audible",audible==lane && !audioBlocked); payload.putInt("outputDevice",outputDevice)
                    if(lanes[lane].wanted) { send(lane,START,payload); updateAudio() } else send(lane,STOP)
                }
                override fun onServiceDisconnected(name:ComponentName) {
                    if(lanes[lane].connection!==this) return
                    if(audible==lane) { audible=-1; ReceiverExtras.setWorkerAudio(site); updateAudio() }
                    synchronized(lanes) { lanes[lane].state=JSONObject().put("state","failed").put("error","Worker process ended") }
                    lanes[lane].remote=null; lanes[lane].wanted=false
                }
            }
            lanes[lane].connection=connection
            try {
                context.applicationContext.startForegroundService(Intent(context,type(lane)))
                if(!context.applicationContext.bindService(Intent(context,type(lane)),connection,Context.BIND_AUTO_CREATE)) throw IllegalStateException()
            } catch(_:Exception) { lanes[lane].wanted=false; lanes[lane].state=JSONObject().put("state","failed").put("error","Could not start receiver service") }
        }
        return true
    }
    @JvmStatic fun stop(lane:Int) { if(lane in 0..3) handler.post { lanes[lane].wanted=false; send(lane,STOP) } }
    @JvmStatic fun listen(lane:Int) {
        if(lane !in -1..3) return
        handler.post { if(site) siteAuto=false; audible=lane; ReceiverExtras.setWorkerAudio(site || lane>=0); updateAudio() }
    }
    private fun updateAudio() { for(i in 0..3) send(i,AUDIO,Bundle().apply { putBoolean("audible",i==audible && !audioBlocked && !(site && siteMuted)); putInt("outputDevice",outputDevice) }) }
    @JvmStatic fun suspendAudio(blocked:Boolean) { handler.post { audioBlocked=blocked; updateAudio() } }
    @JvmStatic fun routeAudio(device:Int) { handler.post { outputDevice=device; updateAudio() } }
    @JvmStatic fun status(context:Context):String {
        app=context.applicationContext
        handler.post {
            thermal=context.getSystemService(PowerManager::class.java).currentThermalStatus>=PowerManager.THERMAL_STATUS_SEVERE
            for(i in 0..3) {
                if(thermal && lanes[i].wanted) { lanes[i].wanted=false; send(i,STOP) }
                send(i,STATUS)
            }
        }
        return synchronized(lanes) { JSONObject().put("lanes",JSONArray(lanes.map { JSONObject(it.state.toString()) })).put("thermalPaused",thermal).put("audible",audible).put("siteCapture",site).put("siteAuto",siteAuto).put("dual",dualArgs!=null).put("voiceFrequency",voiceFrequency).put("voiceTarget",voiceTarget).put("tuneLatencyMs",tuneLatency).put("voicePending",pendingGrant!=null).toString() }
    }
    @JvmStatic fun devices(context:Context):String {
        val usb=context.getSystemService(UsbManager::class.java)
        return JSONArray(usb.deviceList.values.map { JSONObject().put("id",it.deviceName).put("name",it.productName ?: "USB receiver")
            .put("vendor",it.vendorId).put("product",it.productId).put("permitted",usb.hasPermission(it)).put("main",it.deviceName==UsbSourceManager.activeDeviceName()) }).toString()
    }
}

abstract class ReceiverWorkerService:Service() {
    private val handler=Handler(Looper.getMainLooper())
    private var client:Messenger?=null
    private var lane=0
    @Volatile private var state="idle"
    @Volatile private var error=""
    private var engine:Thread?=null
    private var initialized=false
    private var usbConnection:UsbDeviceConnection?=null
    private var wake:PowerManager.WakeLock?=null
    private var serial=0L
    private var startedAt=0L
    private var replay=false
    @Volatile private var audible=false
    private var pending:Bundle?=null
    private var closing=false
    @Volatile private var cancelled=false
    @Volatile private var outputDevice=0
    @Volatile private var request=0L
    @Volatile private var pcmBytes=0L
    @Volatile private var audioBase=LongArray(3)
    private val endpoint=Messenger(Handler(Looper.getMainLooper()) { msg ->
        client=msg.replyTo ?: client; lane=msg.arg1.coerceIn(0,3)
        when(msg.what) {
            ReceiverWorkers.START -> start(msg.data)
            ReceiverWorkers.STOP -> { pending=null; stop() }
            ReceiverWorkers.STATUS -> publish()
            ReceiverWorkers.AUDIO -> { audible=msg.data.getBoolean("audible"); outputDevice=msg.data.getInt("outputDevice"); DsdNative.nativeSetAudioOutputDevice(outputDevice); DsdNative.nativeSuppressLiveAudio(!audible) }
            ReceiverWorkers.TUNE -> {
                val grant=msg.data.getLongArray("grant")
                if(msg.data.getLong("request")==request && state=="running" && !replay && grant!=null) {
                    if(!DsdNative.nativeVoiceTune(grant,msg.data.getInt("modulation"))) { error="Voice tune rejected"; stop() }
                }
                publish()
            }
        }; true
    })
    override fun onBind(intent:Intent):IBinder=endpoint.binder
    override fun onCreate() {
        super.onCreate()
        promote()
    }
    private fun promote() {
        val manager=getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("receiver-workers","XeraX extra receivers",NotificationManager.IMPORTANCE_LOW))
        val open=PendingIntent.getActivity(this,211,Intent(this,DsdNeoActivity::class.java),PendingIntent.FLAG_IMMUTABLE)
        val stop=PendingIntent.getService(this,212,Intent(this,javaClass).setAction("stop"),PendingIntent.FLAG_IMMUTABLE)
        val notification=Notification.Builder(this,"receiver-workers").setSmallIcon(android.R.drawable.ic_media_play)
            .setContentTitle("XeraX SDR").setContentText("Additional receiver / Receptor adicional")
            .setContentIntent(open).addAction(Notification.Action.Builder(null,"Stop / Detener",stop).build()).setOngoing(true).build()
        startForeground(when(this) { is ReceiverWorkerOne -> 211; is ReceiverWorkerTwo -> 212; is ReceiverWorkerThree -> 214; else -> 215 },notification,ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK)
        handler.removeCallbacks(tick); handler.post(tick)
    }
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int { if(intent?.action=="stop") { pending=null; stop() } else { state="starting"; promote() }; return START_NOT_STICKY }
    private fun start(bundle:Bundle) {
        if(engine?.isAlive==true) { pending=Bundle(bundle); stop(); return }
        val raw=bundle.getStringArray("args") ?: return
        request=bundle.getLong("request")
        var args=raw.filter { !it.startsWith("--xerax-") }.toTypedArray()
        cancelled=false; outputDevice=bundle.getInt("outputDevice"); state="starting"; error=""; replay=args.contains("--iq-replay"); audible=bundle.getBoolean("audible")
        pcmBytes=0L
        val wave=File(cacheDir,"worker-$lane-lab.wav")
        if(replay) { wave.delete(); args += arrayOf("-w",wave.absolutePath) }
        val device=bundle.getString("device") ?: ""
        engine=Thread({
            try {
                if(!initialized) {
                    val directory=File(filesDir,"worker-$lane").apply { mkdirs() }
                    check(DsdNative.nativeInit(directory.absolutePath,cacheDir.absolutePath)==0)
                    initialized=true
                }
                if(device.isNotEmpty()) {
                    val manager=getSystemService(UsbManager::class.java)
                    val receiver=manager.deviceList[device] ?: error("USB receiver disconnected")
                    check(manager.hasPermission(receiver)) { "Grant USB access before starting" }
                    usbConnection=manager.openDevice(receiver) ?: error("Could not open USB receiver")
                    if (receiver.vendorId == 0x1d50 && receiver.productId == 0x6089) DsdNative.nativeSetHackrfUsbFd(usbConnection!!.fileDescriptor)
                    else DsdNative.nativeSetUsbFd(usbConnection!!.fileDescriptor)
                }
                DsdNative.nativeSiteCapture(false)
                DsdNative.nativeClearWorkerEvidence()
                DsdNative.nativeEqualizer(raw.contains("--xerax-equalizer"))
                DsdNative.nativeRasReception(raw.contains("--xerax-ras"))
                val offset=raw.firstOrNull { it.startsWith("--xerax-offset=") }?.substringAfter('=')?.toDoubleOrNull() ?: 0.0
                val bandwidth=raw.firstOrNull { it.startsWith("--xerax-bandwidth=") }?.substringAfter('=')?.toIntOrNull() ?: 0
                DsdNative.nativeTrial(offset,bandwidth)
                DsdNative.nativeSharedRate(if(raw.contains("--xerax-shared-rate=192000") && device.isEmpty()) 192000 else 0)
                check(DsdNative.nativeConfigure(args,++serial)==0) { "Receiver configuration failed" }
                audioBase=DsdNative.nativeAudioProgress()
                DsdNative.nativeSetAudioOutputDevice(outputDevice)
                DsdNative.nativeSuppressLiveAudio(!audible)
                wake=getSystemService(PowerManager::class.java).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"XeraX:worker-$lane").apply { acquire() }
                startedAt=SystemClock.elapsedRealtime(); state="running"
                val result=DsdNative.nativeRun()
                state=if(cancelled) "stopped" else if(result==0) "complete" else "failed"
                if(result!=0) error="Decoder failed ($result)"
            } catch(_:Throwable) { state="failed"; error="Receiver could not run; check source and USB access" }
            finally {
                if(replay) { pcmBytes=validPcmBytes(wave); wave.delete() }
                wake?.let { if(it.isHeld) it.release() }; wake=null
                if(!DsdNative.nativeIsUsbFdInUse()) { DsdNative.nativeSetUsbFd(-1); DsdNative.nativeSetHackrfUsbFd(-1); usbConnection?.close(); usbConnection=null }
                handler.post { engine=null; val next=pending; pending=null; if(next!=null && !closing) start(next) else { publish(); handler.removeCallbacks(tick); stopForeground(STOP_FOREGROUND_REMOVE); stopSelf() } }
            }
        },"xerax-worker-$lane").apply { start() }
    }
    private fun validPcmBytes(file:File):Long = try {
        java.io.RandomAccessFile(file,"r").use { input ->
            fun four():String { val b=ByteArray(4); input.readFully(b); return String(b,Charsets.US_ASCII) }
            fun u32():Long=java.lang.Integer.reverseBytes(input.readInt()).toLong() and 0xffffffffL
            if(four()!="RIFF") return 0L
            u32(); if(four()!="WAVE") return 0L
            while(input.filePointer+8<=input.length()) {
                val tag=four(); val count=u32()
                if(count>input.length()-input.filePointer) return 0L
                if(tag=="data") return count
                input.seek(input.filePointer+count+(count and 1L))
            }; 0L
        }
    } catch(_:Exception) { 0L }
    private fun stop() { cancelled=true; if(engine?.isAlive==true) { state="stopping"; DsdNative.nativeStop() } else { state="stopped"; handler.removeCallbacks(tick); stopForeground(STOP_FOREGROUND_REMOVE); stopSelf() }; publish() }
    private fun publish() {
        val status=JSONObject().put("request",request).put("state",state).put("error",error).put("audible",audible)
            .put("pcmBytes",pcmBytes).put("record",DsdNative.nativeNotificationStatus() ?: "").put("elapsedMs",if(startedAt>0) SystemClock.elapsedRealtime()-startedAt else 0)
        val audio=DsdNative.nativeAudioProgress()
        val base=audioBase
        if(audio.size>=3) status.put("pcmFrames",(audio[0]-base[0]).coerceAtLeast(0))
            .put("nonzeroFrames",(audio[1]-base[1]).coerceAtLeast(0)).put("outputFrames",(audio[2]-base[2]).coerceAtLeast(0))
        val current=DecoderStatus.parse(status.optString("record"))
        status.put("frequency",current?.centerFreqHz ?: 0)
        status.put("active",current?.slots?.any { it.state==DecoderStatus.LINE_ACTIVE }==true)
        status.put("talkgroup",current?.leadSlot?.tgText ?: "")
        val tune=DsdNative.nativeVoiceTuneStatus()
        if(tune.size==2) status.put("voiceSequence",tune[0]).put("voiceResult",tune[1])
        if(state in listOf("complete","failed","stopped")) status.put("evidence",DsdNative.nativeWorkerEvidence())
        try { client?.send(Message.obtain(null,ReceiverWorkers.STATUS,lane,0).apply { data=Bundle().apply { putString("status",status.toString()) } }) } catch(_:Exception) { client=null; DsdNative.nativeStop() }
    }
    private val tick=object:Runnable { override fun run() {
        if(state=="running" && (getSystemService(PowerManager::class.java).currentThermalStatus>=PowerManager.THERMAL_STATUS_SEVERE
            || replay && SystemClock.elapsedRealtime()-startedAt>120000)) stop()
        publish(); handler.postDelayed(this,250)
    } }
    override fun onDestroy() { closing=true; pending=null; handler.removeCallbacks(tick); stop(); engine?.join(1500); super.onDestroy() }
}
class ReceiverWorkerOne:ReceiverWorkerService()
class ReceiverWorkerTwo:ReceiverWorkerService()
class ReceiverWorkerThree:ReceiverWorkerService()
class ReceiverWorkerFour:ReceiverWorkerService()
