// SPDX-License-Identifier: GPL-3.0-or-later
package io.github.arancormonk.dsdneo

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.AtomicFile
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.URL
import java.nio.ByteBuffer
import java.security.KeyStore
import java.util.concurrent.ConcurrentHashMap
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.net.ssl.HttpsURLConnection
import org.json.JSONObject

/** Per-user keys only. No shared developer credential or radio samples enter this bridge. */
object AiProviderBridge {
    private val connections = ConcurrentHashMap<Long, HttpsURLConnection>()
    private val cancelled = ConcurrentHashMap.newKeySet<Long>()
    private fun validProvider(p: String) = p == "openai" || p == "deepseek"
    private fun alias(p: String) = "xerax.ai.$p.v1"
    private fun file(c: Context, p: String) = AtomicFile(File(c.noBackupFilesDir, "ai-$p.bin"))
    private fun key(p: String): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias(p), null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias(p), KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setKeySize(256).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    @JvmStatic @Synchronized fun saveKey(c: Context, p: String, value: String): Boolean {
        if (!validProvider(p)) return false
        return try {
            if (value.isEmpty()) { file(c,p).delete(); return true }
            if (value.length !in 16..4096 || value.any { it.code !in 33..126 }) return false
            val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
                init(Cipher.ENCRYPT_MODE,key(p)); updateAAD(p.toByteArray(Charsets.UTF_8))
            }
            val plain = value.toByteArray(Charsets.UTF_8)
            val encrypted = try { cipher.doFinal(plain) } finally { plain.fill(0) }
            val bytes = ByteBuffer.allocate(1 + cipher.iv.size + encrypted.size)
                .put(cipher.iv.size.toByte()).put(cipher.iv).put(encrypted).array()
            val target = file(c,p); val output = target.startWrite()
            try { output.write(bytes); target.finishWrite(output) }
            catch (e: Exception) { target.failWrite(output); return false }
            true
        } catch (_: Exception) { false }
    }
    @JvmStatic @Synchronized fun loadKey(c: Context,p: String): String {
        if (!validProvider(p)) return ""
        return try {
            val bytes = file(c,p).readFully()
            if (bytes.size !in 30..8192 || bytes[0].toInt() != 12) return ""
            val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
                init(Cipher.DECRYPT_MODE,key(p),GCMParameterSpec(128,bytes.copyOfRange(1,13)))
                updateAAD(p.toByteArray(Charsets.UTF_8))
            }
            val plain = cipher.doFinal(bytes,13,bytes.size-13)
            try { String(plain,Charsets.UTF_8) } finally { plain.fill(0) }
        } catch (_: Exception) { "" }
    }
    @JvmStatic fun cancel(id: Long) { cancelled.add(id); connections[id]?.disconnect() }
    @JvmStatic fun request(id: Long,p: String,path: String,secret: String,body: String): String {
        var connection: HttpsURLConnection? = null
        fun result(status: Int,text: String) = JSONObject().put("status",status).put("body",text).toString()
        try {
            if (!validProvider(p) || secret.length !in 16..4096 || secret.any { it.code !in 33..126 }) return result(0,"")
            if (path != "/models" && !(p == "openai" && path == "/responses") && !(p == "deepseek" && path == "/chat/completions")) return result(0,"")
            if (body.length > 100000 || cancelled.contains(id)) return result(0,"")
            val base = if (p == "openai") "https://api.openai.com/v1" else "https://api.deepseek.com"
            connection = URL(base + path).openConnection() as HttpsURLConnection
            connections[id] = connection
            if (cancelled.contains(id)) return result(0,"")
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 12000; connection.readTimeout = 60000
            connection.useCaches = false
            connection.setRequestProperty("Authorization","Bearer $secret")
            connection.setRequestProperty("Accept","application/json")
            connection.requestMethod = if (path == "/models") "GET" else "POST"
            if (connection.requestMethod == "POST") {
                connection.doOutput = true; connection.setRequestProperty("Content-Type","application/json")
                val bytes=body.toByteArray(Charsets.UTF_8); connection.setFixedLengthStreamingMode(bytes.size)
                connection.outputStream.use { it.write(bytes) }
            }
            val status=connection.responseCode
            if (status !in 200..299) return result(status,"") // Provider error bodies can echo credentials; never expose them.
            val output=ByteArrayOutputStream(); val buffer=ByteArray(8192)
            val deadline=System.nanoTime()+90_000_000_000L
            connection.inputStream.use { input ->
                while (true) {
                    if (cancelled.contains(id) || System.nanoTime()>deadline) return result(0,"")
                    val count=input.read(buffer); if (count<0) break
                    if (output.size()+count>1_048_576) return result(0,"")
                    output.write(buffer,0,count)
                }
            }
            return result(status,output.toString("UTF-8"))
        } catch (_: Exception) { return result(0,"") }
        finally { connections.remove(id); cancelled.remove(id); connection?.disconnect() }
    }
}
