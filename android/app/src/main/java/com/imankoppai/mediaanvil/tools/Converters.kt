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
 *
 * Only M4A/AAC is offered today: Android devices ship no Vorbis encoder (so
 * real OGG/Vorbis is impossible), and the Transformer muxer writes MP4 only —
 * a ".flac" file from this chain would be an MP4 container, not a native FLAC,
 * which we refuse to produce. MP3 encoding is likewise not provided by the
 * platform.
 *
 * Transformer must be created and started on a Looper thread (the callbacks
 * arrive there too), so the start runs on Main while the surrounding file
 * work stays off it.
 */
object AudioConverter {
    data class Target(val extension: String, val mimeType: String)

    val targets = listOf(Target("m4a", MimeTypes.AUDIO_AAC))

    /** Bitrates offered for AAC, in kbps. */
    val aacBitratesKbps = listOf(128, 192, 256)
    const val DEFAULT_AAC_BITRATE_KBPS = 192

    fun targetFor(extension: String): Target? =
        targets.firstOrNull { it.extension == extension.lowercase() }

    /**
     * Transcode one document into a cache file; caller streams it back through
     * SAF. The output container is verified afterwards — a completed export
     * with the wrong container is an error, not a success.
     */
    suspend fun convert(context: Context, sourceUri: Uri, target: Target, bitrateKbps: Int = DEFAULT_AAC_BITRATE_KBPS): File {
        val outputFile = File(context.cacheDir, "audio-convert-${System.nanoTime()}.${target.extension}")
        try {
            withContext(Dispatchers.Main) {
                suspendCancellableCoroutine { continuation ->
                    val encoderFactory = androidx.media3.transformer.DefaultEncoderFactory.Builder(context)
                        .setRequestedAudioEncoderSettings(
                            androidx.media3.transformer.AudioEncoderSettings.Builder()
                                .setBitrate(bitrateKbps * 1000)
                                .build(),
                        )
                        .build()
                    val transformer = Transformer.Builder(context)
                        .setAudioMimeType(target.mimeType)
                        .setEncoderFactory(encoderFactory)
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
                            if (continuation.isActive) continuation.resumeWithException(exception)
                        }
                    })
                    transformer.start(MediaItem.fromUri(sourceUri), outputFile.absolutePath)
                }
            }
            verifyOutput(outputFile, target)
            return outputFile
        } catch (failure: Throwable) {
            outputFile.delete()
            throw failure
        }
    }

    /** Assert the produced file really is the container/codec the target promises. */
    fun verifyOutput(output: File, target: Target) {
        val magic = ByteArray(12)
        java.io.RandomAccessFile(output, "r").use { random ->
            if (random.length() < 12) throw IllegalStateException("converted file too small")
            random.readFully(magic)
        }
        val containerOk = when (target.extension) {
            "m4a" -> String(magic, 4, 4) == "ftyp"
            "flac" -> String(magic, 0, 4) == "fLaC"
            "ogg", "opus" -> String(magic, 0, 4) == "OggS"
            else -> true
        }
        if (!containerOk) throw IllegalStateException("wrong container for .${target.extension}")
        val extractor = android.media.MediaExtractor()
        try {
            extractor.setDataSource(output.absolutePath)
            val mimes = (0 until extractor.trackCount).map { extractor.getTrackFormat(it).getString(android.media.MediaFormat.KEY_MIME) }
            if (mimes.none { it == target.mimeType }) {
                throw IllegalStateException("codec mismatch: $mimes")
            }
        } finally {
            extractor.release()
        }
    }
}
