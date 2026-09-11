package com.imankoppai.mediaanvil.tools

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.media.MediaFormat
import android.net.Uri
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.transformer.Transformer
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Supported image conversion targets. BMP needs a hand-rolled encoder (Android has none). */
enum class ImageTarget(val extension: String, val mime: String, val lossy: Boolean) {
    JPG("jpg", "image/jpeg", true),
    PNG("png", "image/png", false),
    WEBP("webp", "image/webp", true),
    BMP("bmp", "image/bmp", true),
}

object ImageConverter {
    /** Decode, flatten transparency onto white for opaque targets, and re-encode. */
    fun convert(bytes: ByteArray, target: ImageTarget, quality: Int): ByteArray {
        val decoded = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
            ?: throw IllegalStateException("invalid_image")
        val source = if ((target == ImageTarget.JPG || target == ImageTarget.BMP) && decoded.hasAlpha()) {
            Bitmap.createBitmap(decoded.width, decoded.height, Bitmap.Config.ARGB_8888).also { flat ->
                flat.eraseColor(android.graphics.Color.WHITE)
                Canvas(flat).drawBitmap(decoded, 0f, 0f, null)
            }
        } else {
            decoded
        }
        val output = when (target) {
            ImageTarget.JPG -> compress(source, Bitmap.CompressFormat.JPEG, quality)
            ImageTarget.PNG -> compress(source, Bitmap.CompressFormat.PNG, 100)
            ImageTarget.WEBP -> compress(
                source,
                if (android.os.Build.VERSION.SDK_INT >= 30) Bitmap.CompressFormat.WEBP_LOSSY else Bitmap.CompressFormat.WEBP,
                quality,
            )
            ImageTarget.BMP -> BmpEncoder.encode(source)
        }
        if (source !== decoded) source.recycle()
        decoded.recycle()
        return output
    }

    private fun compress(bitmap: Bitmap, format: Bitmap.CompressFormat, quality: Int): ByteArray =
        ByteArrayOutputStream().use { stream ->
            if (!bitmap.compress(format, quality.coerceIn(1, 100), stream)) error("encode_failed")
            stream.toByteArray()
        }
}

/** Minimal 24-bit uncompressed BMP writer (bottom-up, BGR, 4-byte row padding). */
object BmpEncoder {
    fun encode(bitmap: Bitmap): ByteArray {
        val width = bitmap.width
        val height = bitmap.height
        val rowSize = (width * 3 + 3) / 4 * 4
        val imageSize = rowSize * height
        val fileSize = 54 + imageSize
        val buffer = ByteBuffer.allocate(fileSize).order(ByteOrder.LITTLE_ENDIAN)
        buffer.put(0x42); buffer.put(0x4D) // 'B','M'
        buffer.putInt(fileSize)
        buffer.putInt(0)
        buffer.putInt(54)
        buffer.putInt(40) // BITMAPINFOHEADER
        buffer.putInt(width)
        buffer.putInt(height)
        buffer.putShort(1) // planes
        buffer.putShort(24) // bits per pixel
        buffer.putInt(0) // BI_RGB
        buffer.putInt(imageSize)
        buffer.putInt(2835); buffer.putInt(2835) // 72 DPI
        buffer.putInt(0); buffer.putInt(0)
        val row = IntArray(width)
        for (y in height - 1 downTo 0) {
            bitmap.getPixels(row, 0, width, 0, y, width, 1)
            var written = 0
            for (pixel in row) {
                buffer.put((pixel and 0xFF).toByte())          // blue
                buffer.put((pixel shr 8 and 0xFF).toByte())    // green
                buffer.put((pixel shr 16 and 0xFF).toByte())   // red
                written += 3
            }
            repeat(rowSize - written) { buffer.put(0) }
        }
        return buffer.array()
    }
}

/**
 * Audio transcoding through the platform encoders via Media3 Transformer.
 * MP3 encoding is not provided by Android devices, so it is not offered.
 */
object AudioConverter {
    data class Target(val extension: String, val mimeType: String)

    val targets = listOf(
        Target("m4a", MimeTypes.AUDIO_AAC),
        Target("flac", MimeTypes.AUDIO_FLAC),
        Target("ogg", MimeTypes.AUDIO_VORBIS),
    )

    fun targetFor(extension: String): Target? =
        targets.firstOrNull { it.extension == extension.lowercase() }

    /** Transcode one document into a cache file; caller streams it back through SAF. */
    suspend fun convert(context: Context, sourceUri: Uri, target: Target): File =
        withContext(Dispatchers.IO) {
            val outputFile = File(context.cacheDir, "audio-convert-${System.nanoTime()}.${target.extension}")
            suspendCancellableCoroutine { continuation ->
                val transformer = Transformer.Builder(context)
                    .setAudioMimeType(target.mimeType)
                    .build()
                continuation.invokeOnCancellation { transformer.cancel() }
                transformer.addListener(object : Transformer.Listener {
                    override fun onCompleted(composition: androidx.media3.transformer.Composition, result: androidx.media3.transformer.ExportResult) {
                        if (continuation.isActive) continuation.resume(outputFile)
                    }

                    override fun onError(
                        composition: androidx.media3.transformer.Composition,
                        result: androidx.media3.transformer.ExportResult,
                        exception: androidx.media3.transformer.ExportException,
                    ) {
                        outputFile.delete()
                        if (continuation.isActive) continuation.resumeWithException(exception)
                    }
                })
                transformer.start(MediaItem.fromUri(sourceUri), outputFile.absolutePath)
            }
        }
}
