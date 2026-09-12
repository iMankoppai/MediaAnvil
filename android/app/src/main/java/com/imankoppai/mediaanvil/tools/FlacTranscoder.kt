package com.imankoppai.mediaanvil.tools

import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Transcode any playable audio into a NATIVE FLAC file (fLaC stream), which
 * media3's Transformer cannot mux (it would produce FLAC frames inside an MP4
 * container). Pipeline: MediaCodec decode to PCM -> platform FLAC encoder ->
 * hand-written FLAC stream: "fLaC" + STREAMINFO (patched after encoding) +
 * concatenated encoder frames.
 */
object FlacTranscoder {
    class FlacException(message: String) : Exception(message)

    suspend fun transcode(sourcePath: String, output: File) {
        val extractor = MediaExtractor()
        try {
            extractor.setDataSource(sourcePath)
        } catch (error: Exception) {
            extractor.release()
            throw FlacException("cannot open source: ${error.message}")
        }
        var trackIndex = -1
        var inputFormat: MediaFormat? = null
        for (i in 0 until extractor.trackCount) {
            val candidate = extractor.getTrackFormat(i)
            if (candidate.getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true) {
                trackIndex = i
                inputFormat = candidate
                break
            }
        }
        if (trackIndex < 0 || inputFormat == null) {
            extractor.release()
            throw FlacException("no audio track")
        }
        extractor.selectTrack(trackIndex)
        val sampleRate = inputFormat.getInteger(MediaFormat.KEY_SAMPLE_RATE)
        val channels = inputFormat.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
        try {
            transcodeLoop(extractor, inputFormat, sampleRate, channels, output)
        } catch (error: Exception) {
            throw error
        } finally {
            extractor.release()
        }
    }

    private suspend fun transcodeLoop(
        extractor: MediaExtractor,
        inputFormat: MediaFormat,
        sampleRate: Int,
        channels: Int,
        output: File,
    ) {
        val decoderMime = inputFormat.getString(MediaFormat.KEY_MIME)!!
        var decoderRef: MediaCodec? = null
        var encoderRef: MediaCodec? = null
        var framesRef: RandomAccessFile? = null
        var encoderStarted = false
        var decoderStarted = false
        try {
            val decoder = MediaCodec.createDecoderByType(decoderMime)
            decoderRef = decoder
            val encoder = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_AUDIO_FLAC)
            encoderRef = encoder
            val frames = RandomAccessFile(output, "rw")
            framesRef = frames
            decoder.configure(inputFormat, null, null, 0)
            decoder.start()
            decoderStarted = true
            val encoderFormat = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_FLAC, sampleRate, channels)
                .apply { setInteger(MediaFormat.KEY_PCM_ENCODING, AudioFormat.ENCODING_PCM_16BIT) }
            encoder.configure(encoderFormat, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
            encoder.start()
            encoderStarted = true

            // Reserve: fLaC + STREAMINFO block header + 34-byte STREAMINFO.
            frames.setLength(0)
            frames.write(byteArrayOf(0x66, 0x4C, 0x61, 0x43)) // fLaC
            frames.write(byteArrayOf(0x80.toByte(), 0, 0, 34)) // last-block STREAMINFO, length 34
            frames.write(ByteArray(34))

            var decoderEosQueued = false
            var decoderOutputDone = false
            var encoderEosQueued = false
            var encoderOutputDone = false
            var totalSamples = 0L
            var minBlockSize = -1
            var maxBlockSize = -1
            val decoderInfo = MediaCodec.BufferInfo()
            val encoderInfo = MediaCodec.BufferInfo()
            val frameBytes = channels * 2
            var pendingPcm: ByteBuffer? = null
            var pendingPresentationTimeUs = 0L
            var pendingFramesFed = 0

            while (!encoderOutputDone) {
                currentCoroutineContext().ensureActive()
                // 1. Feed the decoder until its source is exhausted.
                if (!decoderEosQueued) {
                    val index = decoder.dequeueInputBuffer(10_000L)
                    if (index >= 0) {
                        val buffer = decoder.getInputBuffer(index)!!
                        val size = extractor.readSampleData(buffer, 0)
                        if (size < 0) {
                            decoder.queueInputBuffer(index, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            decoderEosQueued = true
                        } else {
                            decoder.queueInputBuffer(index, 0, size, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }
                // 2. Hold at most one copied PCM chunk. Releasing the decoder
                // output immediately prevents decoder/encoder back-pressure from
                // deadlocking on long or high-resolution input.
                if (pendingPcm == null && !decoderOutputDone) {
                    val outIndex = decoder.dequeueOutputBuffer(decoderInfo, if (decoderEosQueued) 0L else 10_000L)
                    if (outIndex >= 0) {
                        val pcm = decoder.getOutputBuffer(outIndex)!!
                        if (decoderInfo.size > 0) {
                            pcm.position(decoderInfo.offset)
                            pcm.limit(decoderInfo.offset + decoderInfo.size)
                            val normalized = convertTo16Bit(pcm, decoder.outputFormat)
                            val copied = ByteBuffer.allocate(normalized.remaining()).order(ByteOrder.LITTLE_ENDIAN)
                            copied.put(normalized)
                            copied.flip()
                            pendingPcm = copied
                            pendingPresentationTimeUs = decoderInfo.presentationTimeUs
                            pendingFramesFed = 0
                        }
                        decoder.releaseOutputBuffer(outIndex, false)
                        if (decoderInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) {
                            decoderOutputDone = true
                        }
                    }
                }
                // 3. Feed one encoder buffer, then drain encoder output before
                // asking for another input buffer.
                pendingPcm?.let { pcm ->
                    val index = encoder.dequeueInputBuffer(0L)
                    if (index >= 0) {
                        val input = encoder.getInputBuffer(index)!!
                        input.clear()
                        val byteCount = minOf(pcm.remaining(), input.remaining(), 4096 * frameBytes)
                        val alignedByteCount = byteCount - byteCount % frameBytes
                        if (alignedByteCount <= 0) throw FlacException("encoder input buffer is too small")
                        val oldLimit = pcm.limit()
                        pcm.limit(pcm.position() + alignedByteCount)
                        input.put(pcm)
                        pcm.limit(oldLimit)
                        val sampleCount = alignedByteCount / frameBytes
                        encoder.queueInputBuffer(
                            index,
                            0,
                            alignedByteCount,
                            pendingPresentationTimeUs + pendingFramesFed * 1_000_000L / sampleRate,
                            0,
                        )
                        pendingFramesFed += sampleCount
                        totalSamples += sampleCount
                        if (!pcm.hasRemaining()) pendingPcm = null
                    }
                }
                // 4. Once the decoder and pending PCM are done, queue encoder EOS.
                if (decoderOutputDone && pendingPcm == null && !encoderEosQueued) {
                    val index = encoder.dequeueInputBuffer(0L)
                    if (index >= 0) {
                        encoder.queueInputBuffer(index, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                        encoderEosQueued = true
                    }
                }
                // 5. Drain encoded FLAC frames. Codec-config contains the
                // encoder's own fLaC/STREAMINFO header; skip it because this
                // writer owns and patches the file header above.
                while (true) {
                    val encIndex = encoder.dequeueOutputBuffer(encoderInfo, 0L)
                    if (encIndex >= 0) {
                        val buffer = encoder.getOutputBuffer(encIndex)!!
                        if (encoderInfo.size > 0 && encoderInfo.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG == 0) {
                            buffer.position(encoderInfo.offset)
                            buffer.limit(encoderInfo.offset + encoderInfo.size)
                            val bytes = ByteArray(encoderInfo.size)
                            buffer.get(bytes)
                            val blockSize = parseFrameBlockSize(bytes)
                            if (blockSize > 0) {
                                minBlockSize = if (minBlockSize < 0) blockSize else minOf(minBlockSize, blockSize)
                                maxBlockSize = maxOf(maxBlockSize, blockSize)
                            }
                            frames.seek(frames.length())
                            frames.write(bytes)
                        }
                        encoder.releaseOutputBuffer(encIndex, false)
                        if (encoderInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) {
                            encoderOutputDone = true
                        }
                    } else {
                        break
                    }
                }
            }
            if (!encoderOutputDone) throw FlacException("encoder did not finish")
            if (minBlockSize < 0) minBlockSize = 4096
            if (maxBlockSize < 0) maxBlockSize = minBlockSize

            writeStreamInfo(frames, sampleRate, channels, totalSamples, minBlockSize, maxBlockSize)
        } finally {
            encoderRef?.let { codec ->
                if (encoderStarted) runCatching { codec.stop() }
                runCatching { codec.release() }
            }
            decoderRef?.let { codec ->
                if (decoderStarted) runCatching { codec.stop() }
                runCatching { codec.release() }
            }
            runCatching { framesRef?.close() }
        }
    }

    /** Normalize whatever PCM encoding the decoder produced to 16-bit. */
    private fun convertTo16Bit(buffer: ByteBuffer, outputFormat: MediaFormat): ByteBuffer {
        val encoding = if (outputFormat.containsKey(MediaFormat.KEY_PCM_ENCODING)) {
            outputFormat.getInteger(MediaFormat.KEY_PCM_ENCODING)
        } else AudioFormat.ENCODING_PCM_16BIT
        if (encoding == AudioFormat.ENCODING_PCM_16BIT) return buffer
        val out = ByteBuffer.allocate(buffer.remaining() / 2).order(ByteOrder.LITTLE_ENDIAN)
        when (encoding) {
            AudioFormat.ENCODING_PCM_24BIT_PACKED -> {
                val bytes = ByteArray(buffer.remaining())
                buffer.get(bytes)
                var i = 0
                while (i + 2 < bytes.size) {
                    val v = (bytes[i].toInt() and 0xFF) or ((bytes[i + 1].toInt() and 0xFF) shl 8) or
                        ((bytes[i + 2].toInt() and 0xFF) shl 16).let { if (bytes[i + 2].toInt() and 0x80 != 0) it or (0xFF shl 24) else it }
                    out.putShort((v shr 8).toShort())
                    i += 3
                }
            }
            AudioFormat.ENCODING_PCM_32BIT -> {
                while (buffer.remaining() >= 4) {
                    out.putShort((buffer.int shr 16).toShort())
                }
            }
            AudioFormat.ENCODING_PCM_FLOAT -> {
                while (buffer.remaining() >= 4) {
                    out.putShort((buffer.float * 32767f).toInt().coerceIn(-32768, 32767).toShort())
                }
            }
            AudioFormat.ENCODING_PCM_8BIT -> {
                while (buffer.remaining() >= 1) {
                    out.putShort((((buffer.get().toInt() and 0xFF) - 128) * 256).toShort())
                }
            }
        }
        out.flip()
        return out
    }

    /** Return the block size encoded in a FLAC frame header, or -1 if invalid. */
    internal fun parseFrameBlockSize(frame: ByteArray): Int {
        if (frame.size < 5 || frame[0] != 0xFF.toByte() || frame[1].toInt() and 0xFC != 0xF8) return -1
        val code = (frame[2].toInt() shr 4) and 0xF
        val frameNumberBytes = utf8IntegerLength(frame[4].toInt() and 0xFF)
        if (frameNumberBytes < 0) return -1
        val extraOffset = 4 + frameNumberBytes
        return when (code) {
            1 -> 192
            in 2..5 -> 576 shl (code - 2)
            6 -> if (extraOffset < frame.size) (frame[extraOffset].toInt() and 0xFF) + 1 else -1
            7 -> if (extraOffset + 1 < frame.size) {
                ((frame[extraOffset].toInt() and 0xFF) shl 8 or
                    (frame[extraOffset + 1].toInt() and 0xFF)) + 1
            } else -1
            in 8..15 -> 256 shl (code - 8)
            else -> -1
        }
    }

    private fun utf8IntegerLength(firstByte: Int): Int = when {
        firstByte and 0x80 == 0 -> 1
        firstByte and 0xE0 == 0xC0 -> 2
        firstByte and 0xF0 == 0xE0 -> 3
        firstByte and 0xF8 == 0xF0 -> 4
        firstByte and 0xFC == 0xF8 -> 5
        firstByte and 0xFE == 0xFC -> 6
        firstByte == 0xFE -> 7
        else -> -1
    }

    /** Patch the 34-byte STREAMINFO payload after "fLaC" and its 4-byte block header. */
    internal fun writeStreamInfo(
        frames: RandomAccessFile,
        sampleRate: Int,
        channels: Int,
        totalSamples: Long,
        minBlockSize: Int,
        maxBlockSize: Int,
    ) {
        val info = ByteArray(34)
        val bits = BitWriter(info)
        bits.write(minBlockSize.toLong(), 16)
        bits.write(maxBlockSize.toLong(), 16)
        bits.write(0, 24) // min frame size unknown
        bits.write(0, 24) // max frame size unknown
        bits.write(sampleRate.toLong(), 20)
        bits.write((channels - 1).toLong(), 3)
        bits.write(15L, 5) // 16 bits per sample
        bits.write(totalSamples, 36)
        // MD5 of unencoded audio left zeroed (= unknown), players accept this.
        frames.seek(8)
        frames.write(info)
    }

    private class BitWriter(private val target: ByteArray) {
        private var byteIndex = 0
        private var bitIndex = 7

        fun write(value: Long, bitCount: Int) {
            for (i in bitCount - 1 downTo 0) {
                val bit = ((value shr i) and 1L).toInt()
                if (bit == 1) target[byteIndex] = (target[byteIndex].toInt() or (1 shl bitIndex)).toByte()
                if (bitIndex == 0) {
                    byteIndex++
                    bitIndex = 7
                } else {
                    bitIndex--
                }
            }
        }
    }
}
