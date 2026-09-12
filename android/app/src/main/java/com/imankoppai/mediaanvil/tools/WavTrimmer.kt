package com.imankoppai.mediaanvil.tools

import android.content.Context
import android.net.Uri
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Lossless WAV trimming: streams the PCM bytes between two timestamps into a new
 * RIFF/WAVE file with the original format, optionally applying linear fades at
 * sample level. Supports integer PCM of 16/24/32 bits.
 */
object WavTrimmer {
    class WavException(message: String) : Exception(message)

    data class Format(
        val channels: Int,
        val sampleRate: Int,
        val bitsPerSample: Int,
        val dataOffset: Long,
        val dataLength: Long,
    ) {
        val frameBytes: Int get() = channels * bitsPerSample / 8
    }

    fun parseFormat(context: Context, uri: Uri): Format {
        context.contentResolver.openInputStream(uri)?.use { input ->
            val riff = ByteArray(12)
            input.readFully(riff)
            if (String(riff, 0, 4) != "RIFF" || String(riff, 8, 4) != "WAVE") {
                throw WavException("not a RIFF/WAVE file")
            }
            var channels = 0
            var sampleRate = 0
            var bits = 0
            var audioFormat = 0
            var dataOffset = -1L
            var dataLength = -1L
            val header = ByteArray(8)
            var position = 12L
            while (true) {
                if (input.readFullyOrNull(header) == null) break
                val id = String(header, 0, 4)
                val size = leInt(header, 4)
                position += 8
                if (id == "fmt ") {
                    val payload = ByteArray(size)
                    input.readFully(payload)
                    position += size
                    val buffer = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN)
                    audioFormat = buffer.short.toInt()
                    channels = buffer.short.toInt()
                    sampleRate = buffer.int
                    buffer.int // byte rate
                    buffer.short // block align
                    bits = buffer.short.toInt()
                } else if (id == "data") {
                    dataOffset = position
                    dataLength = size.toLong()
                    break
                } else {
                    input.skipFully(size.toLong())
                    position += size
                }
                if (size % 2 == 1) {
                    input.skipFully(1)
                    position += 1
                }
            }
            if (audioFormat != 1) throw WavException("unsupported WAV encoding $audioFormat (PCM only)")
            if (channels !in 1..8 || sampleRate <= 0) throw WavException("bad fmt chunk")
            if (bits !in intArrayOf(16, 24, 32)) throw WavException("unsupported bit depth $bits")
            if (dataOffset < 0) throw WavException("data chunk missing")
            return Format(channels, sampleRate, bits, dataOffset, dataLength)
        } ?: throw WavException("cannot open source")
    }

    /**
     * Stream-trim [startMs]..[endMs] into [output], applying optional linear fades.
     * Returns the written duration in ms.
     */
    fun trim(
        context: Context,
        uri: Uri,
        format: Format,
        startMs: Long,
        endMs: Long,
        fadeInMs: Long,
        fadeOutMs: Long,
        output: File,
    ): Long {
        val frameBytes = format.frameBytes
        val totalFrames = format.dataLength / frameBytes
        val startFrame = (startMs * format.sampleRate / 1000).coerceIn(0, totalFrames)
        val endFrame = (endMs * format.sampleRate / 1000).coerceIn(startFrame, totalFrames)
        val frames = endFrame - startFrame
        if (frames <= 0) throw WavException("empty range")
        val fadeInFrames = ((fadeInMs * format.sampleRate / 1000).coerceAtMost(frames / 2)).toInt()
        val fadeOutFrames = ((fadeOutMs * format.sampleRate / 1000).coerceAtMost(frames / 2)).toInt()
        val dataBytes = frames * frameBytes

        context.contentResolver.openInputStream(uri)?.use { input ->
            input.skipFully(format.dataOffset + startFrame * frameBytes)
            output.outputStream().use { out ->
                writeHeader(out, format, dataBytes)
                val buffer = ByteArray(((1 shl 16) / frameBytes) * frameBytes)
                var written = 0L
                while (written < dataBytes) {
                    val toRead = minOf(buffer.size.toLong(), dataBytes - written).toInt()
                    input.readFully(buffer, 0, toRead)
                    applyFades(
                        buffer, toRead, frameBytes, format.bitsPerSample,
                        fadeInFrames, fadeOutFrames, totalFrames, startFrame + written / frameBytes,
                    )
                    out.write(buffer, 0, toRead)
                    written += toRead
                }
            }
        } ?: throw WavException("cannot open source")
        return frames * 1000L / format.sampleRate
    }

    /** Apply linear fade-in/out ramps to the sample frames in [buffer]. */
    private fun applyFades(
        buffer: ByteArray,
        length: Int,
        frameBytes: Int,
        bits: Int,
        fadeInFrames: Int,
        fadeOutFrames: Int,
        totalFrames: Long,
        firstFrame: Long,
    ) {
        val frames = length / frameBytes
        var offset = 0
        repeat(frames) {
            val frame = firstFrame + it
            var gain = 1f
            if (fadeInFrames > 0 && frame < fadeInFrames) gain = frame.toFloat() / fadeInFrames
            if (fadeOutFrames > 0 && frame > totalFrames - fadeOutFrames) {
                val out = (totalFrames - frame).toFloat() / fadeOutFrames
                if (out < gain) gain = out
            }
            if (gain < 1f) scaleSample(buffer, offset, bits, gain)
            offset += frameBytes
        }
    }

    private fun scaleSample(bytes: ByteArray, offset: Int, bits: Int, gain: Float) {
        when (bits) {
            16 -> {
                val value = ((bytes[offset].toInt() and 0xFF) or (bytes[offset + 1].toInt() shl 8)).toShort()
                val scaled = (value * gain).toInt().coerceIn(Short.MIN_VALUE.toInt(), Short.MAX_VALUE.toInt())
                bytes[offset] = (scaled and 0xFF).toByte()
                bytes[offset + 1] = ((scaled shr 8) and 0xFF).toByte()
            }
            24 -> {
                val value = ((bytes[offset].toInt() and 0xFF) or
                    ((bytes[offset + 1].toInt() and 0xFF) shl 8) or
                    ((bytes[offset + 2].toInt() and 0xFF) shl 16)).let { if (it and 0x800000 != 0) it or 0xFF000000.toInt() else it }
                val scaled = (value * gain).toInt()
                bytes[offset] = (scaled and 0xFF).toByte()
                bytes[offset + 1] = ((scaled shr 8) and 0xFF).toByte()
                bytes[offset + 2] = ((scaled shr 16) and 0xFF).toByte()
            }
            32 -> {
                val value = ByteBuffer.wrap(bytes, offset, 4).order(ByteOrder.LITTLE_ENDIAN).int
                val scaled = (value * gain).toInt()
                ByteBuffer.wrap(bytes, offset, 4).order(ByteOrder.LITTLE_ENDIAN).putInt(scaled)
            }
        }
    }

    private fun writeHeader(out: OutputStream, format: Format, dataBytes: Long) {
        val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        header.put("RIFF".toByteArray())
        header.putInt((36 + dataBytes).toInt())
        header.put("WAVE".toByteArray())
        header.put("fmt ".toByteArray())
        header.putInt(16)
        header.putShort(1) // PCM
        header.putShort(format.channels.toShort())
        header.putInt(format.sampleRate)
        header.putInt(format.sampleRate * format.frameBytes)
        header.putShort(format.frameBytes.toShort())
        header.putShort(format.bitsPerSample.toShort())
        header.put("data".toByteArray())
        header.putInt(dataBytes.toInt())
        out.write(header.array())
    }

    private fun leInt(bytes: ByteArray, offset: Int): Int =
        (bytes[offset].toInt() and 0xFF) or
            ((bytes[offset + 1].toInt() and 0xFF) shl 8) or
            ((bytes[offset + 2].toInt() and 0xFF) shl 16) or
            ((bytes[offset + 3].toInt() and 0xFF) shl 24)

    private fun InputStream.readFully(buffer: ByteArray) {
        var read = 0
        while (read < buffer.size) {
            val n = read(buffer, read, buffer.size - read)
            if (n < 0) throw WavException("unexpected end of file")
            read += n
        }
    }

    private fun InputStream.readFully(buffer: ByteArray, offset: Int, length: Int) {
        var read = 0
        while (read < length) {
            val n = read(buffer, offset + read, length - read)
            if (n < 0) throw WavException("unexpected end of file")
            read += n
        }
    }

    private fun InputStream.readFullyOrNull(buffer: ByteArray): ByteArray? {
        var read = 0
        while (read < buffer.size) {
            val n = read(buffer, read, buffer.size - read)
            if (n < 0) return if (read == 0) null else buffer
            read += n
        }
        return buffer
    }

    private fun InputStream.skipFully(count: Long) {
        var remaining = count
        val scratch = ByteArray(1 shl 16)
        while (remaining > 0) {
            val skipped = skip(remaining)
            if (skipped > 0) {
                remaining -= skipped
            } else {
                val n = read(scratch, 0, minOf(scratch.size.toLong(), remaining).toInt())
                if (n < 0) throw WavException("unexpected end of file")
                remaining -= n
            }
        }
    }
}
