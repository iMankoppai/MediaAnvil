package com.imankoppai.mediaanvil.data

import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import androidx.documentfile.provider.DocumentFile
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.File
import java.io.InputStream
import java.io.OutputStream

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

    /** Copy a document off the UI thread and stop promptly when its job is cancelled. */
    suspend fun copyToCacheCancellable(context: Context, uri: Uri, displayName: String): File =
        withContext(Dispatchers.IO) {
            val extension = displayName.substringAfterLast('.', "tmp")
            val target = File(cacheDir(context), "${System.nanoTime()}-${Thread.currentThread().id}.$extension")
            try {
                context.contentResolver.openInputStream(uri)?.use { input ->
                    target.outputStream().use { output -> copyCancellable(input, output) }
                } ?: throw IllegalStateException("open_failed")
                if (target.length() == 0L) throw IllegalStateException("empty_document")
                target
            } catch (failure: Throwable) {
                target.delete()
                throw failure
            }
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

    /** Save a converted/derived file next to its source with `_n` collision avoidance. */
    fun saveConvertedDocument(
        context: Context,
        parent: DocumentFile,
        sourceName: String,
        newExtension: String,
        edited: File,
    ): Uri {
        val stem = sourceName.substringBeforeLast('.', sourceName)
        var candidate = "$stem.$newExtension"
        var index = 1
        while (parent.findFile(candidate) != null) {
            candidate = "${stem}_$index.$newExtension"
            index++
        }
        val created = parent.createFile("application/octet-stream", candidate)
            ?: throw IllegalStateException("create_failed")
        writeAndVerify(context, created.uri, edited)
        return created.uri
    }

    /** Cancellable variant for long conversions; removes a partial output on failure. */
    suspend fun saveConvertedDocumentCancellable(
        context: Context,
        parent: DocumentFile,
        sourceName: String,
        newExtension: String,
        edited: File,
    ): Uri = withContext(Dispatchers.IO) {
        val stem = sourceName.substringBeforeLast('.', sourceName)
        var candidate = "$stem.$newExtension"
        var index = 1
        while (parent.findFile(candidate) != null) {
            currentCoroutineContext().ensureActive()
            candidate = "${stem}_$index.$newExtension"
            index++
        }
        val created = parent.createFile("application/octet-stream", candidate)
            ?: throw IllegalStateException("create_failed")
        try {
            writeAndVerifyCancellable(context, created.uri, edited)
            created.uri
        } catch (failure: Throwable) {
            runCatching { created.delete() }
            throw failure
        }
    }

    /**
     * In-place overwrite for documents picked outside the granted tree:
     * OpenDocument grants write access to the returned document itself.
     */
    fun overwriteInPlace(context: Context, target: Uri, edited: File) {
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

    fun queryDisplayName(context: Context, uri: Uri): String? =
        context.contentResolver.query(
            uri,
            arrayOf(android.provider.OpenableColumns.DISPLAY_NAME),
            null,
            null,
            null,
        )?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else null
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

    private suspend fun writeAndVerifyCancellable(context: Context, target: Uri, edited: File) {
        context.contentResolver.openOutputStream(target, "wt")?.use { output ->
            edited.inputStream().use { input -> copyCancellable(input, output) }
        } ?: throw IllegalStateException("open_output_failed")
        val written = context.contentResolver.openInputStream(target)?.use { input ->
            countCancellable(input)
        } ?: -1L
        if (written != edited.length()) throw IllegalStateException("verify_failed")
    }

    private suspend fun copyCancellable(input: InputStream, output: OutputStream): Long {
        var count = 0L
        val buffer = ByteArray(256 * 1024)
        while (true) {
            currentCoroutineContext().ensureActive()
            val read = input.read(buffer)
            if (read < 0) return count
            output.write(buffer, 0, read)
            count += read
        }
    }

    private suspend fun countCancellable(input: InputStream): Long {
        var count = 0L
        val buffer = ByteArray(256 * 1024)
        while (true) {
            currentCoroutineContext().ensureActive()
            val read = input.read(buffer)
            if (read < 0) return count
            count += read
        }
    }
}
