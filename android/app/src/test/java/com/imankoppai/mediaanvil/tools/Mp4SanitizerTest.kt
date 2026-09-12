package com.imankoppai.mediaanvil.tools

import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

class Mp4SanitizerTest {
    @Test
    fun downgradesOnlyMalformedVersionOneEditList() {
        val file = File.createTempFile("mediaanvil", ".m4a").apply { deleteOnExit() }
        val bytes = ByteArray(28).also {
            it[0] = 0
            it[1] = 0
            it[2] = 0
            it[3] = 28
            it[4] = 'e'.code.toByte()
            it[5] = 'l'.code.toByte()
            it[6] = 's'.code.toByte()
            it[7] = 't'.code.toByte()
            it[8 + 0] = 1 // version 1 with a version-0-sized entry below
            it[8 + 4 + 3] = 1 // entry_count = 1 (big-endian)
            it[20] = 0x12
            it[21] = 0x34
            it[22] = 0x56
            it[23] = 0x78 // truncated v1 duration low word
        }
        file.writeBytes(bytes)

        AudioConverter.sanitizeMp4EditLists(file)

        val sanitized = file.readBytes()
        assertEquals(0, sanitized[8].toInt())
        assertEquals(0x12, sanitized[16].toInt() and 0xFF)
        assertEquals(0x34, sanitized[17].toInt() and 0xFF)
        assertEquals(0x56, sanitized[18].toInt() and 0xFF)
        assertEquals(0x78, sanitized[19].toInt() and 0xFF)
        assertEquals(0, sanitized[20].toInt())
        assertEquals(0, sanitized[21].toInt())
        assertEquals(0, sanitized[22].toInt())
        assertEquals(0, sanitized[23].toInt())
        assertEquals(0, sanitized[24].toInt())
        assertEquals(1, sanitized[25].toInt())
        assertEquals(0, sanitized[26].toInt())
        assertEquals(0, sanitized[27].toInt())
    }
}
