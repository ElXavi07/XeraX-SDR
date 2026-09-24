// SPDX-License-Identifier: GPL-3.0-or-later
package io.github.arancormonk.dsdneo
import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import java.io.File
object CallExport {
    /** Export only to the directory explicitly selected by the user through SAF. */
    @JvmStatic fun export(context:Context,path:String,tree:String):String {
        val created=mutableListOf<Uri>()
        return try {
            val wave=File(path).canonicalFile
            require(wave.path.startsWith(context.filesDir.canonicalPath+File.separator) && wave.extension=="wav")
            val meta=File(wave.parentFile,wave.nameWithoutExtension+".json")
            require(wave.isFile && meta.isFile)
            val root=Uri.parse(tree)
            require(root.scheme=="content" && DocumentsContract.isTreeUri(root))
            val resolver=context.contentResolver
            val id=DocumentsContract.getTreeDocumentId(root)
            val parent=DocumentsContract.buildDocumentUriUsingTree(root,id)
            val children=DocumentsContract.buildChildDocumentsUriUsingTree(root,id)
            resolver.query(children,arrayOf(DocumentsContract.Document.COLUMN_DISPLAY_NAME),null,null,null)?.use { cursor ->
                while(cursor.moveToNext()) require(cursor.getString(0)!=wave.name && cursor.getString(0)!=meta.name)
            }
            for(file in listOf(wave,meta)) {
                val uri=DocumentsContract.createDocument(resolver,parent,if(file==wave) "audio/wav" else "application/json",file.name) ?: error("create")
                created.add(uri)
                resolver.openOutputStream(uri,"w")?.use { out -> file.inputStream().use { it.copyTo(out,65536) } } ?: error("write")
            }
            ""
        } catch(_:Exception) {
            for(uri in created) try { DocumentsContract.deleteDocument(context.contentResolver,uri) } catch(_:Exception) { }
            ReceiverExtras.text("Export failed. Choose a writable folder without files of the same name.","No se pudo exportar. Elige una carpeta con permiso de escritura y sin archivos del mismo nombre.")
        }
    }
}
