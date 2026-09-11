package com.imankoppai.mediaanvil.subtitles

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class SubtitleFormatsTest {
    @Test
    fun formatsLrcTimestampsWithHalfUpRounding() {
        assertEquals("[00:01.50]", SubtitleFormats.lrcTimestamp(1_500))
        assertEquals("[01:01.50]", SubtitleFormats.lrcTimestamp(61_500))
        assertEquals("[00:01.50]", SubtitleFormats.lrcTimestamp(1_499))
        assertEquals("[59:59.99]", SubtitleFormats.lrcTimestamp(3_599_990))
        assertEquals("[00:00.00]", SubtitleFormats.lrcTimestamp(0))
    }

    @Test
    fun detectsLrcTimestamps() {
        assertTrue(SubtitleFormats.hasLrcTimestamp("[00:01.50]hello"))
        assertTrue(SubtitleFormats.hasLrcTimestamp("[01:01]hello"))
        assertFalse(SubtitleFormats.hasLrcTimestamp("plain text"))
        assertFalse(SubtitleFormats.hasLrcTimestamp("[ti:title]"))
    }

    @Test
    fun validatesEmbeddableLyrics() {
        assertThrows(IllegalArgumentException::class.java) {
            SubtitleFormats.validateEmbeddableLyrics("   ")
        }
        assertThrows(IllegalArgumentException::class.java) {
            SubtitleFormats.validateEmbeddableLyrics("no timestamps here")
        }
        SubtitleFormats.validateEmbeddableLyrics("[00:01.00]ok")
    }

    @Test
    fun convertsSrtToLrcKeepingEachTextLine() {
        val srt = """
            1
            00:00:02,000 --> 00:00:04,500
            First line
            Second line
        """.trimIndent()

        val lrc = SubtitleFormats.timedTextToLrc(srt)

        assertEquals("[00:02.00]First line\n[00:02.00]Second line\n", lrc)
    }

    @Test
    fun convertsVttToLrc() {
        val vtt = """
            WEBVTT

            01:02.250 --> 01:05.000
            Whispering
        """.trimIndent()

        val lrc = SubtitleFormats.timedTextToLrc(vtt)

        assertEquals("[01:02.25]Whispering\n", lrc)
    }

    @Test
    fun rejectsTimedTextWithoutValidCues() {
        assertThrows(IllegalArgumentException::class.java) {
            SubtitleFormats.timedTextToLrc("no cues at all")
        }
    }

    @Test
    fun detectsTimedSubtitles() {
        assertTrue(SubtitleFormats.looksLikeTimed("00:00:02,000 --> 00:00:04,500"))
        assertTrue(SubtitleFormats.looksLikeTimed("01:02.250 --> 01:05.000"))
        assertFalse(SubtitleFormats.looksLikeTimed("[00:01.00]lyric line"))
    }

    @Test
    fun convertsLrcToSrtWithInferredEndTimes() {
        val lrc = "[00:01.00]First line\n[00:04.00]Second line"

        val srt = SubtitleFormats.convertSubtitle(lrc, "lrc", "srt")

        assertEquals(
            "1\n00:00:01,000 --> 00:00:04,000\nFirst line\n\n" +
                "2\n00:00:04,000 --> 00:00:09,000\nSecond line\n",
            srt,
        )
    }

    @Test
    fun convertsLrcToVttWithHeader() {
        val vtt = SubtitleFormats.convertSubtitle("[00:01.00]Hello", "lrc", "vtt")

        assertEquals("WEBVTT\n\n00:00:01.000 --> 00:00:06.000\nHello\n", vtt)
    }

    @Test
    fun convertsSrtToVttRoundTrip() {
        val srt = "1\n00:00:02,000 --> 00:00:04,500\nDeep line"
        val vtt = SubtitleFormats.convertSubtitle(srt, "srt", "vtt")
        assertEquals("WEBVTT\n\n00:00:02.000 --> 00:00:04.500\nDeep line\n", vtt)
        val backToSrt = SubtitleFormats.convertSubtitle(vtt, "vtt", "srt")
        assertEquals(srt + "\n", backToSrt)
    }

    @Test
    fun rendersSrtTimestampsWithHoursAndHalfUpRounding() {
        assertEquals("01:00:00,000", SubtitleFormats.subtitleTimestamp(3_600_000, ","))
        assertEquals("00:59:59,999", SubtitleFormats.subtitleTimestamp(3_599_999, ","))
        assertEquals("00:00:00,000", SubtitleFormats.subtitleTimestamp(0, ","))
    }

    @Test
    fun parsesLrcTimelineKeepingLastLineHighlighted() {
        val cues = PreviewLyrics.parseLrcTimeline("[00:01.50]First\n[00:04.00]Second")

        assertEquals(2, cues.size)
        assertEquals(1_500L, cues[0].startMs)
        assertEquals(4_000L, cues[0].endMs)
        assertEquals(4_000L, cues[1].startMs)
        assertEquals(PreviewLyrics.NO_END, cues[1].endMs)
    }

    @Test
    fun lrcTimelineIgnoresMetadataAndUsesLastTimestampText() {
        val cues = PreviewLyrics.parseLrcTimeline("[ti:Title]\n[00:01.00][00:05.00]Chorus")

        assertEquals(2, cues.size)
        assertEquals("Chorus", cues[0].text)
        assertEquals("Chorus", cues[1].text)
        assertEquals(1_000L, cues[0].startMs)
        assertEquals(5_000L, cues[0].endMs)
    }
}
