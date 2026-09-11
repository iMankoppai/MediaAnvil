package com.imankoppai.mediaanvil.subtitles

import org.junit.Assert.assertEquals
import org.junit.Test

class SubtitleParserTest {
    @Test
    fun parsesLrcAndUsesNextCueAsEnd() {
        val cues = SubtitleParser.parseLrc("[00:01.50]First\n[00:04.00]Second")

        assertEquals(2, cues.size)
        assertEquals(1_500L, cues[0].startMs)
        assertEquals(4_000L, cues[0].endMs)
        assertEquals("Second", cues[1].text)
    }

    @Test
    fun parsesSrtMultilineCue() {
        val cues = SubtitleParser.parseTimedBlocks(
            """
            1
            00:00:02,000 --> 00:00:04,500
            First line
            Second line
            """.trimIndent(),
        )

        assertEquals(1, cues.size)
        assertEquals(2_000L, cues.single().startMs)
        assertEquals(4_500L, cues.single().endMs)
        assertEquals("First line\nSecond line", cues.single().text)
    }

    @Test
    fun parsesWebVttWithoutHourComponent() {
        val cues = SubtitleParser.parseTimedBlocks(
            """
            WEBVTT

            01:02.250 --> 01:05.000
            Whispering
            """.trimIndent(),
        )

        assertEquals(1, cues.size)
        assertEquals(62_250L, cues.single().startMs)
        assertEquals(65_000L, cues.single().endMs)
    }
}
