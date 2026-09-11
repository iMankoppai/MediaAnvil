package com.imankoppai.mediaanvil.data

import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import androidx.documentfile.provider.DocumentFile
import java.io.File

/**
 * SAF bridge for tag editing: jaudiotagger needs real files, so edits run on a
 * cache copy and are streamed back afterwards. The source document is only
 * deleted after the replacement has been fully written and verified.
 */
object DocumentOps {
    private const val TMP_SUFFIX = ".mediaanvil-tmp"

    fun cacheDir(context: Context): File = File(context.cacheDir, "tagedit").apply { mkdirs() }

    /** Copy a document into the cache with its original extension preserved. */
    fun copyToCache(context: Context, uri: Uri, displayName: String): File {
        val extension = displayName.substringAfterLast('.', "tmp")
        val target = File(cacheDir(context), "${System.nanoTime()}-${Thread.currentThread().id}.$extension")
        context.contentResolver.openInputStream(uri)?.use { input ->
            target.outputStream().use { output -> input.copyTo(output) }
        } ?: throw IllegalStateException("open_failed")
        if (target.length() == 0L) {
            target.delete()
            throw IllegalStateException("empty_document")
        }
        return target
    }

    fun deleteCache(file: File) {
        runCatching { file.delete() }
    }

    /**
     * Overwrite the source document with the edited cache copy: write a new
     * document first, verify it, then delete the original and rename. If the
     * final rename fails the staged copy keeps a temporary name so nothing is
     * silently lost.
     */
    fun overwriteDocument(context: Context, parent: DocumentFile, sourceName: String, edited: File): Uri {
        val staged = parent.createFile("application/octet-stream", sourceName + TMP_SUFFIX)
            ?: throw IllegalStateException("create_failed")
        try {
            writeAndVerify(context, staged.uri, edited)
        } catch (failure: Exception) {
            runCatching { staged.delete() }
            throw failure
        }
        val original = parent.findFile(sourceName)
        if (original != null && original.uri != staged.uri && !original.delete()) {
            throw IllegalStateException("delete_original_failed")
        }
        return try {
            DocumentsContract.renameDocument(context.contentResolver, staged.uri, sourceName) ?: staged.uri
        } catch (first: Exception) {
            runCatching { DocumentsContract.renameDocument(context.contentResolver, staged.uri, sourceName + TMP_SUFFIX) ?: staged.uri }
                .getOrDefault(staged.uri)
        }
    }

    /** Save-as with the desktop `_tagged` naming and collision avoidance. */
    fun saveAsDocument(context: Context, parent: DocumentFile, sourceName: String, edited: File): Uri {
        val stem = sourceName.substringBeforeLast('.')
        val extension = sourceName.substringAfterLast('.', "bin")
        var candidate = "${stem}_tagged.$extension"
        var index = 1
        while (parent.findFile(candidate) != null) {
            candidate = "${stem}_tagged_$index.$extension"
            index++
        }
        val created = parent.createFile("application/octet-stream", candidate)
            ?: throw IllegalStateException("create_failed")
        writeAndVerify(context, created.uri, edited)
        return created.uri
    }

    private fun writeAndVerify(context: Context, target: Uri, edited: File) {
        context.contentResolver.openOutputStream(target, "wt")?.use { output ->
            edited.inputStream().use { input -> input.copyTo(output) }
        } ?: throw IllegalStateException("open_output_failed")
        val written = context.contentResolver.openInputStream(target)?.use { stream ->
            var count = 0L
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val read = stream.read(buffer)
                if (read < 0) break
                count += read
            }
            count
        } ?: -1L
        if (written != edited.length()) throw IllegalStateException("verify_failed")
    }
}
