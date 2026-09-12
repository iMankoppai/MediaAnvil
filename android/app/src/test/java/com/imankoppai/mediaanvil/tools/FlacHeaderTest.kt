package com.imankoppai.mediaanvil.tools

import org.junit.Assert.assertEquals
import org.junit.Assert.assertArrayEquals
import org.junit.Test
import java.io.RandomAccessFile

class FlacHeaderTest {
    @Test
    fun fixedBlockSizeCodesAreParsed() {
        assertEquals(192, FlacTranscoder.parseFrameBlockSize(header(blockCode = 1)))
        assertEquals(576, FlacTranscoder.parseFrameBlockSize(header(blockCode = 2)))
        assertEquals(4096, FlacTranscoder.parseFrameBlockSize(header(blockCode = 12)))
    }

    @Test
    fun explicitBlockSizeFollowsVariableLengthFrameNumber() {
        assertEquals(
            1000,
            FlacTranscoder.parseFrameBlockSize(
                header(blockCode = 7, frameNumber = byteArrayOf(0xC2.toByte(), 0x80.toByte()), extra = byteArrayOf(0x03, 0xE7.toByte())),
            ),
        )
    }

    @Test
    fun invalidHeaderIsRejected() {
        assertEquals(-1, FlacTranscoder.parseFrameBlockSize(byteArrayOf(0x66, 0x4C, 0x61, 0x43)))
    }

    @Test
    fun streamInfoStartsImmediatelyAfterMetadataHeader() {
        val file = kotlin.io.path.createTempFile(suffix = ".flac").toFile().apply { deleteOnExit() }
        RandomAccessFile(file, "rw").use { output ->
            output.write(byteArrayOf(0x66, 0x4C, 0x61, 0x43, 0x80.toByte(), 0, 0, 34))
            output.write(ByteArray(34))
            FlacTranscoder.writeStreamInfo(output, 48_000, 2, 48_000, 4096, 4096)
        }
        val bytes = file.readBytes()
        assertArrayEquals(
            byteArrayOf(0x66, 0x4C, 0x61, 0x43, 0x80.toByte(), 0, 0, 34, 0x10, 0x00),
            bytes.copyOfRange(0, 10),
        )
    }

    private fun header(
        blockCode: Int,
        frameNumber: ByteArray = byteArrayOf(0),
        extra: ByteArray = byteArrayOf(),
    ): ByteArray = byteArrayOf(
        0xFF.toByte(),
        0xF8.toByte(),
        (blockCode shl 4).toByte(),
        0,
        *frameNumber,
        *extra,
        0,
    )
}
