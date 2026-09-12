package com.imankoppai.mediaanvil.tools

import android.annotation.SuppressLint
import android.content.Context
import androidx.media3.muxer.Muxer
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.media.MediaFormat
import android.net.Uri
import android.os.Build
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
 * Audio transcoding through the platform encoders.
 *
 * - M4A/AAC and Opus-in-OGG via Media3 Transformer (Opus-in-OGG needs this
 *   custom muxer because media3's own muxers only write MP4/WebM).
 * - FLAC via a custom decode -> platform FLAC encoder -> native fLaC container
 *   pipeline, because media3 has no FLAC muxer (a ".flac" out of Transformer
 *   would be an MP4 container).
 * - OGG/Vorbis and MP3 are impossible: the platform ships no Vorbis or MP3
 *   encoders, and bundling one means a native-library project.
 *
 * Transformer must be created and started on a Looper thread (callbacks arrive
 * there too), so starts run on Main while file work stays off it.
 */
@SuppressLint("UnsafeOptInUsageError")
object AudioConverter {
    data class Target(val extension: String, val mimeType: String)

    class InsufficientStorageException(val requiredBytes: Long, val availableBytes: Long) :
        Exception("insufficient temporary storage")

    private val allTargets = listOf(
        Target("m4a", MimeTypes.AUDIO_AAC),
        Target("flac", MimeTypes.AUDIO_FLAC),
        Target("opus", MimeTypes.AUDIO_OPUS),
    )

    /** Opus encoding and the platform OGG muxer both require Android 10. */
    val targets: List<Target>
        get() = allTargets.filter { it.extension != "opus" || Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q }

    /** Bitrates offered for AAC, in kbps. */
    val aacBitratesKbps = listOf(128, 192, 256)
    const val DEFAULT_AAC_BITRATE_KBPS = 192

    fun targetFor(extension: String): Target? =
        targets.firstOrNull { it.extension == extension.lowercase() }

    /**
     * Reserve room for the cache output and the final SAF copy. This is exact
     * for known duration/sample formats and deliberately conservative when
     * metadata is unavailable.
     */
    fun requireTemporarySpace(context: Context, source: File, target: Target, bitrateKbps: Int) {
        val estimatedOutput = estimateOutputBytes(source, target, bitrateKbps)
        val required = estimatedOutput.coerceAtMost(Long.MAX_VALUE / 2) * 2 + SPACE_SAFETY_BYTES
        val available = context.cacheDir.usableSpace
        if (available < required) throw InsufficientStorageException(required, available)
    }

    private fun estimateOutputBytes(source: File, target: Target, bitrateKbps: Int): Long {
        val extractor = android.media.MediaExtractor()
        return try {
            extractor.setDataSource(source.absolutePath)
            val format = (0 until extractor.trackCount)
                .map { extractor.getTrackFormat(it) }
                .firstOrNull { it.getString(android.media.MediaFormat.KEY_MIME)?.startsWith("audio/") == true }
            val durationUs = format?.getLongOrNull(android.media.MediaFormat.KEY_DURATION)
            if (durationUs == null || durationUs <= 0) return fallbackOutputBytes(source, target)
            val seconds = durationUs / 1_000_000.0
            val bytes = if (target.extension == "flac") {
                val sampleRate = format.getIntegerOrNull(android.media.MediaFormat.KEY_SAMPLE_RATE)
                    ?: return fallbackOutputBytes(source, target)
                val channels = format.getIntegerOrNull(android.media.MediaFormat.KEY_CHANNEL_COUNT)
                    ?: return fallbackOutputBytes(source, target)
                seconds * sampleRate * channels * 2.0
            } else {
                seconds * bitrateKbps * 1000.0 / 8.0
            }
            (bytes * 1.15).toLong().coerceAtLeast(MIN_ESTIMATED_OUTPUT_BYTES)
        } catch (_: Exception) {
            fallbackOutputBytes(source, target)
        } finally {
            extractor.release()
        }
    }

    private fun fallbackOutputBytes(source: File, target: Target): Long =
        (source.length() * if (target.extension == "flac") 8L else 2L)
            .coerceAtLeast(MIN_ESTIMATED_OUTPUT_BYTES)

    private fun android.media.MediaFormat.getLongOrNull(key: String): Long? =
        if (containsKey(key)) getLong(key) else null

    private fun android.media.MediaFormat.getIntegerOrNull(key: String): Int? =
        if (containsKey(key)) getInteger(key) else null

    /**
     * Transcode one document into a cache file; caller streams it back through
     * SAF. The output container is verified afterwards — a completed export
     * with the wrong container is an error, not a success.
     */
    suspend fun convert(context: Context, source: File, target: Target, bitrateKbps: Int = DEFAULT_AAC_BITRATE_KBPS): File {
        val outputFile = File(context.cacheDir, "audio-convert-${System.nanoTime()}.${target.extension}")
        try {
            when (target.extension) {
                "flac" -> withContext(Dispatchers.IO) {
                    FlacTranscoder.transcode(source.absolutePath, outputFile)
                }
                "opus" -> runTransformer(
                    context, Uri.fromFile(source), outputFile, target.mimeType, bitrateKbps,
                    OggMuxerFactory(),
                )
                else -> runTransformer(
                    context, Uri.fromFile(source), outputFile, target.mimeType, bitrateKbps,
                    null,
                ).also { sanitizeMp4EditLists(outputFile) }
            }
            verifyOutput(outputFile, target)
            return outputFile
        } catch (failure: Throwable) {
            outputFile.delete()
            throw failure
        }
    }

    /** Create and start a Transformer on a Looper thread; suspend until it finishes. */
    private suspend fun runTransformer(
        context: Context,
        sourceUri: Uri,
        outputFile: File,
        mimeType: String,
        bitrateKbps: Int,
        muxerFactory: Muxer.Factory?,
    ) = withContext(Dispatchers.Main) {
        suspendCancellableCoroutine { continuation ->
            val encoderFactory = androidx.media3.transformer.DefaultEncoderFactory.Builder(context)
                .setRequestedAudioEncoderSettings(
                    androidx.media3.transformer.AudioEncoderSettings.Builder()
                        .setBitrate(bitrateKbps * 1000)
                        .build(),
                )
                .build()
            val builder = Transformer.Builder(context)
                .setAudioMimeType(mimeType)
                .setEncoderFactory(encoderFactory)
            if (muxerFactory != null) builder.setMuxerFactory(muxerFactory)
            val transformer = builder.build()
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
        if (!containerOk) throw IllegalStateException(
            "wrong container for .${target.extension}: first bytes ${magic.joinToString(" ") { "%02X".format(it) }}",
        )
        val extractor = android.media.MediaExtractor()
        try {
            extractor.setDataSource(output.absolutePath)
            val mimes = (0 until extractor.trackCount).map { extractor.getTrackFormat(it).getString(android.media.MediaFormat.KEY_MIME) }
            // Android's native FLAC extractor decodes frames itself and exposes
            // its track as audio/raw even though the file container is FLAC.
            val codecOk = if (target.extension == "flac") {
                mimes.any { it == target.mimeType || it == MimeTypes.AUDIO_RAW }
            } else {
                mimes.any { it == target.mimeType }
            }
            if (!codecOk) {
                throw IllegalStateException("codec mismatch: $mimes")
            }
        } finally {
            extractor.release()
        }
    }

    /**
     * Some Android MediaMuxer builds emit a version-1 `elst` atom containing
     * version-0 (32-bit) entries. FFmpeg can decode it, but Media3's MP4
     * extractor rejects it while opening the exported M4A. Re-layout the
     * truncated version-1 fields as a valid version-0 entry; valid edit lists
     * are left untouched.
     */
    internal fun sanitizeMp4EditLists(output: File) {
        val bytes = output.readBytes()
        var changed = false
        var cursor = 4
        while (cursor + 16 <= bytes.size) {
            if (bytes[cursor] == 0x65.toByte() && bytes[cursor + 1] == 0x6C.toByte() &&
                bytes[cursor + 2] == 0x73.toByte() && bytes[cursor + 3] == 0x74.toByte()
            ) {
                val atomStart = cursor - 4
                val atomSize = readBigEndianInt(bytes, atomStart)
                if (atomStart >= 0 && atomSize >= 16 && atomStart + atomSize <= bytes.size) {
                    val version = bytes[cursor + 4].toInt() and 0xFF
                    val entryCount = readBigEndianInt(bytes, cursor + 8).toLong()
                    val v0Size = 16L + entryCount * 12L
                    val v1Size = 16L + entryCount * 20L
                    if (version == 1 && entryCount > 0 && atomSize.toLong() >= v0Size &&
                        atomSize.toLong() < v1Size
                    ) {
                        bytes[cursor + 4] = 0
                        val entriesStart = cursor + 12
                        for (index in 0 until entryCount.toInt()) {
                            val entryStart = entriesStart + index * 12
                            // MediaMuxer wrote the low 32 bits of the v1
                            // segment duration in the second half of the
                            // truncated entry. Preserve that duration while
                            // restoring the v0 media_time and media_rate.
                            val segmentDuration = readBigEndianInt(bytes, entryStart + 4)
                            writeBigEndianInt(bytes, entryStart, segmentDuration)
                            writeBigEndianInt(bytes, entryStart + 4, 0)
                            writeBigEndianInt(bytes, entryStart + 8, 0x00010000)
                        }
                        changed = true
                    }
                }
            }
            cursor++
        }
        if (changed) output.outputStream().use { it.write(bytes) }
    }

    private fun readBigEndianInt(bytes: ByteArray, offset: Int): Int =
        ((bytes[offset].toInt() and 0xFF) shl 24) or
            ((bytes[offset + 1].toInt() and 0xFF) shl 16) or
            ((bytes[offset + 2].toInt() and 0xFF) shl 8) or
            (bytes[offset + 3].toInt() and 0xFF)

    private fun writeBigEndianInt(bytes: ByteArray, offset: Int, value: Int) {
        bytes[offset] = (value ushr 24).toByte()
        bytes[offset + 1] = (value ushr 16).toByte()
        bytes[offset + 2] = (value ushr 8).toByte()
        bytes[offset + 3] = value.toByte()
    }

    private const val MIN_ESTIMATED_OUTPUT_BYTES = 4L * 1024 * 1024
    private const val SPACE_SAFETY_BYTES = 64L * 1024 * 1024
}
