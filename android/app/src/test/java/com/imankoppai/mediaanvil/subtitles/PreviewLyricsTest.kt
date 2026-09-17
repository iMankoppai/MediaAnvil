package com.imankoppai.mediaanvil.subtitles

import org.junit.Assert.assertEquals
import org.junit.Test

class PreviewLyricsTest {
    @Test
    fun lrcTimelineKeepsLastLineHighlighted() {
        val cues = PreviewLyrics.parseLrcTimeline("[00:01.50]First\n[00:04.00]Second")

        assertEquals(2, cues.size)
        assertEquals(1_500L, cues[0].startMs)
        assertEquals(4_000L, cues[0].endMs)
        assertEquals(4_000L, cues[1].startMs)
        assertEquals(PreviewLyrics.NO_END, cues[1].endMs)
    }

    @Test
    fun lrcTimelineIgnoresMetadataAndSupportsRepeatedTimestamps() {
        val cues = PreviewLyrics.parseLrcTimeline("[ti:Title]\n[00:01.00][00:05.00]Chorus")

        assertEquals(2, cues.size)
        assertEquals("Chorus", cues[0].text)
        assertEquals("Chorus", cues[1].text)
        assertEquals(1_000L, cues[0].startMs)
        assertEquals(5_000L, cues[0].endMs)
    }

    @Test
    fun lrcTimelineMergesOriginalAndTranslationAtSameTimestamp() {
        val cues = PreviewLyrics.parseLrcTimeline(
            "[00:02.00]Hello world\n[00:02.00]你好，世界\n[00:05.00]Next",
        )

        assertEquals(2, cues.size)
        assertEquals("Hello world\n你好，世界", cues[0].text)
        assertEquals(2_000L, cues[0].startMs)
        assertEquals(5_000L, cues[0].endMs)
    }
}
