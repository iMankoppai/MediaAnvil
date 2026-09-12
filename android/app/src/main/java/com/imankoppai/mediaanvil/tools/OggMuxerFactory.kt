package com.imankoppai.mediaanvil.tools

import android.annotation.SuppressLint
import android.media.MediaCodec
import android.media.MediaFormat
import android.media.MediaMuxer
import android.os.Build
import androidx.annotation.RequiresApi
import androidx.media3.common.Format
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.muxer.BufferInfo
import androidx.media3.muxer.Muxer
import com.google.common.collect.ImmutableList

/**
 * Transformer muxer that writes a real OGG container (MuxerOutput.OGG via the
 * platform MediaMuxer, Android 10+) so Opus audio can be exported as a
 * standard .opus file. media3's own muxers only write MP4/WebM.
 */
@UnstableApi
class OggMuxerFactory : Muxer.Factory {
    @SuppressLint("NewApi") // Guarded explicitly so the factory can exist on minSdk 26.
    override fun create(path: String): Muxer {
        check(Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            "Ogg/Opus export requires Android 10 or newer"
        }
        return OggMuxer(path)
    }

    override fun getSupportedSampleMimeTypes(trackType: Int): ImmutableList<String> =
        if (trackType == androidx.media3.common.C.TRACK_TYPE_AUDIO) {
            ImmutableList.of(MimeTypes.AUDIO_OPUS)
        } else {
            ImmutableList.of()
        }

    @RequiresApi(Build.VERSION_CODES.Q)
    private class OggMuxer(path: String) : Muxer {
        private val mediaMuxer = MediaMuxer(path, MediaMuxer.OutputFormat.MUXER_OUTPUT_OGG)
        private var trackIndex = -1
        private var started = false
        private var released = false

        override fun addTrack(format: Format): Int {
            check(trackIndex < 0) { "OGG output supports one audio track" }
            val mediaFormat = MediaFormat.createAudioFormat(
                MimeTypes.AUDIO_OPUS,
                format.sampleRate,
                format.channelCount,
            )
            format.initializationData.forEachIndexed { index, data ->
                mediaFormat.setByteBuffer("csd-$index", java.nio.ByteBuffer.wrap(data))
            }
            trackIndex = mediaMuxer.addTrack(mediaFormat)
            return trackIndex
        }

        override fun writeSampleData(trackIndex: Int, buffer: java.nio.ByteBuffer, info: BufferInfo) {
            check(trackIndex == this.trackIndex) { "unknown OGG track" }
            if (!started) {
                mediaMuxer.start()
                started = true
            }
            val mediaInfo = MediaCodec.BufferInfo()
            val mediaCodecFlags = info.flags and
                (MediaCodec.BUFFER_FLAG_KEY_FRAME or MediaCodec.BUFFER_FLAG_END_OF_STREAM)
            mediaInfo.set(buffer.position(), info.size, info.presentationTimeUs, mediaCodecFlags)
            mediaMuxer.writeSampleData(trackIndex, buffer, mediaInfo)
        }

        override fun addMetadataEntry(entry: androidx.media3.common.Metadata.Entry) {
            // OGG metadata via MediaMuxer is not supported; tags stay empty.
        }

        override fun close() {
            if (released) return
            try {
                if (started) mediaMuxer.stop()
            } finally {
                mediaMuxer.release()
                released = true
            }
        }
    }
}
