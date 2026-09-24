// SPDX-License-Identifier: GPL-3.0-or-later
package io.github.arancormonk.dsdneo
import android.content.Context
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import org.json.JSONObject

/** Service lifetime only: secret-bearing argv stays in memory and dies with the process. */
object ReceiverSession {
    private val handler=Handler(Looper.getMainLooper())
    @Volatile private var captureRestore:Array<String>?=null
    @Volatile private var lastArgs:Array<String>?=null
    @Volatile private var captureDeadline=0L
    @Volatile private var restoreCount=0L
    @Volatile private var recoveryArgs:Array<String>?=null
    @Volatile private var recoveryIdentity=""
    @Volatile private var recoverySerial=""
    @Volatile private var recoveryUntil=0L
    @Volatile private var recoveryText=""
    @Volatile private var stoppedByUser=false
    @Volatile var service:DecoderService?=null
    @JvmStatic fun configureRecovery(context:Context,enabled:Boolean) {
        context.getSharedPreferences("receiver-service",Context.MODE_PRIVATE).edit().putBoolean("usbRecovery",enabled).apply()
        if(!enabled) cancelRecovery()
    }
    @Synchronized fun begin(args:Array<String>) {
        stoppedByUser=false; lastArgs=args.copyOf(); handler.removeCallbacks(deadline)
        if(args.contains("--iq-capture")) {
            val restored=mutableListOf<String>(); var i=0
            while(i<args.size) {
                if(args[i] in listOf("--iq-capture","--iq-capture-max-mb","--iq-capture-format")) i+=2
                else { restored.add(args[i]); i++ }
            }
            captureRestore=restored.toTypedArray(); captureDeadline=0
        } else captureRestore=null
    }
    @Synchronized fun running() {
        if(captureRestore!=null) { captureDeadline=SystemClock.elapsedRealtime()+20000; handler.postDelayed(deadline,20000) }
    }
    private val deadline=Runnable { if(captureRestore!=null && !stoppedByUser) DsdNative.nativeStop() }
    @Synchronized fun completed(success:Boolean):Array<String>? {
        handler.removeCallbacks(deadline)
        val resume=if(success && !stoppedByUser && !awaitingUsb()) captureRestore else null
        captureRestore=null; captureDeadline=0
        if(resume!=null) restoreCount++
        return resume
    }
    @Synchronized fun userStop() { stoppedByUser=true; captureRestore=null; lastArgs=null; captureDeadline=0; handler.removeCallbacks(deadline); cancelRecovery(); ReceiverWorkers.stopAll() }
    @Synchronized private fun cancelRecovery() { recoveryArgs=null; recoveryIdentity=""; recoverySerial=""; recoveryUntil=0; recoveryText="" }
    fun detached(context:Context,device:UsbDevice?) {
        if(device==null || stoppedByUser || !context.getSharedPreferences("receiver-service",Context.MODE_PRIVATE).getBoolean("usbRecovery",false)) return
        val serial=try { device.serialNumber ?: "" } catch(_:Exception) { "" }
        if(serial.isEmpty()) { recoveryText="Reconnect the receiver and tap Retry / Reconecte y pulse Reintentar"; return }
        recoveryArgs=lastArgs?.copyOf(); recoverySerial=serial; recoveryIdentity="${device.vendorId}:${device.productId}"
        recoveryUntil=SystemClock.elapsedRealtime()+60000; recoveryText="Waiting for the same USB receiver / Esperando el mismo receptor USB"
        handler.postDelayed({ if(recoveryArgs!=null && SystemClock.elapsedRealtime()>=recoveryUntil) { cancelRecovery(); service?.finishRecoveryWait() } },61000)
    }
    fun awaitingUsb():Boolean=recoveryArgs!=null && SystemClock.elapsedRealtime()<recoveryUntil
    fun attached(context:Context,device:UsbDevice) {
        if(!awaitingUsb() || "${device.vendorId}:${device.productId}"!=recoveryIdentity) return
        val manager=context.getSystemService(UsbManager::class.java)
        if(!manager.hasPermission(device)) { recoveryText="USB access required; open XeraX / Abra XeraX para permitir acceso USB"; return }
        val serial=try { device.serialNumber ?: "" } catch(_:Exception) { "" }
        if(serial!=recoverySerial) return
        UsbSourceManager.requestAccessForSource(context,"usb",serial.takeLast(16))
        fun attempt(remaining:Int) {
            if(!awaitingUsb()) return
            if(UsbSourceManager.isReady() && !DsdNative.nativeIsRunning()) {
                val args=recoveryArgs ?: return; cancelRecovery(); service?.resumeFromService(args)
            } else if(remaining>0) handler.postDelayed({ attempt(remaining-1) },250)
        }
        handler.postDelayed({ attempt(12) },250)
    }
    @JvmStatic fun status(context:Context):String=JSONObject()
        .put("captureActive",captureRestore!=null).put("captureSeconds",if(captureDeadline>0) ((captureDeadline-SystemClock.elapsedRealtime()).coerceAtLeast(0)/1000) else 0)
        .put("captureRestored",restoreCount).put("recoveryEnabled",context.getSharedPreferences("receiver-service",Context.MODE_PRIVATE).getBoolean("usbRecovery",false))
        .put("recovery",recoveryText).toString()
}
