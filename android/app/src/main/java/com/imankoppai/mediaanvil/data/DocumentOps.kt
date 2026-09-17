package com.imankoppai.mediaanvil.data

import android.content.Context
import android.net.Uri
import java.io.File

/** Small SAF bridge used by the two-field tag editor. */
object DocumentOps {
    private const val CACHE_FOLDER = "tag-edit"

    fun cacheDir(context: Context): File = File(context.cacheDir, CACHE_FOLDER).apply { mkdirs() }

    fun copyToCache(context: Context, uri: Uri, displayName: String): File {
        val extension = displayName.substringAfterLast('.', "tmp")
        val target = File(cacheDir(context), "${System.nanoTime()}.$extension")
        try {
            context.contentResolver.openInputStream(uri)?.use { input ->
                target.outputStream().use { output -> input.copyTo(output) }
            } ?: error("open_failed")
            check(target.length() > 0L) { "empty_document" }
            return target
        } catch (failure: Throwable) {
            target.delete()
            throw failure
        }
    }

    fun deleteCache(file: File) {
        runCatching { file.delete() }
    }

    /** Write an edited copy and restore the original copy if the provider fails. */
    fun overwriteInPlace(context: Context, target: Uri, edited: File, original: File) {
        try {
            writeAndVerify(context, target, edited)
        } catch (failure: Throwable) {
            runCatching { writeAndVerify(context, target, original) }
            throw failure
        }
    }

    private fun writeAndVerify(context: Context, target: Uri, source: File) {
        context.contentResolver.openOutputStream(target, "wt")?.use { output ->
            source.inputStream().use { input -> input.copyTo(output) }
        } ?: error("open_output_failed")
        val written = context.contentResolver.openInputStream(target)?.use { input ->
            val buffer = ByteArray(64 * 1024)
            var count = 0L
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                count += read
            }
            count
        } ?: -1L
        check(written == source.length()) { "verify_failed" }
    }
}
