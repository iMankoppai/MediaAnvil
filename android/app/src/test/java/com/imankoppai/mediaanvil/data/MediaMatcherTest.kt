package com.imankoppai.mediaanvil.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MediaMatcherTest {
    private fun file(name: String) = MediaMatcher.FileRef(name, "")

    @Test
    fun prefersFullAudioNameOverExactMatch() {
        val candidates = MediaMatcher.bestCandidates(
            "song.flac",
            listOf(file("song.lrc"), file("song.flac.lrc")),
            MediaMatcher.lyricExtensions,
        )

        assertEquals(listOf("song.flac.lrc"), candidates.files.map { it.name })
        assertEquals(MediaMatcher.Priority.FULL_AUDIO_NAME, candidates.priority)
        assertFalse(candidates.ambiguous)
    }

    @Test
    fun keepsExactMatchWhenNoFullNameVariant() {
        val candidates = MediaMatcher.bestCandidates(
            "song.mp3",
            listOf(file("song.lrc"), file("other.lrc")),
            MediaMatcher.lyricExtensions,
        )

        assertEquals(listOf("song.lrc"), candidates.files.map { it.name })
        assertEquals(MediaMatcher.Priority.EXACT, candidates.priority)
    }

    @Test
    fun ignoresSpacesAtLowerPriority() {
        val candidates = MediaMatcher.bestCandidates(
            "My Song.mp3",
            listOf(file("My  Song.lrc")),
            MediaMatcher.lyricExtensions,
        )

        assertEquals(MediaMatcher.Priority.IGNORE_SPACES, candidates.priority)
        assertEquals(1, candidates.files.size)
    }

    @Test
    fun stripsCopySuffixesAtLowestPriority() {
        for (name in listOf("Song - 副本.lrc", "Song - copy 2.lrc", "Song (1).lrc", "Song（2）.lrc")) {
            val candidates = MediaMatcher.bestCandidates("Song.mp3", listOf(file(name)), MediaMatcher.lyricExtensions)
            assertEquals(name, MediaMatcher.Priority.COPY_SUFFIX, candidates.priority)
        }
    }

    @Test
    fun retainsAllTiedCandidatesAsAmbiguous() {
        val candidates = MediaMatcher.bestCandidates(
            "song.mp3",
            listOf(file("song.lrc"), file("song.srt"), file("song.vtt")),
            MediaMatcher.lyricExtensions,
        )

        assertTrue(candidates.ambiguous)
        assertNull(candidates.single)
        assertEquals(3, candidates.files.size)
    }

    @Test
    fun keepsOnlyTheBestPriority() {
        val candidates = MediaMatcher.bestCandidates(
            "song.flac",
            listOf(file("song.lrc"), file("song.flac.srt"), file("song.flac.vtt")),
            MediaMatcher.lyricExtensions,
        )

        assertEquals(MediaMatcher.Priority.FULL_AUDIO_NAME, candidates.priority)
        assertEquals(2, candidates.files.size)
        assertTrue(candidates.ambiguous)
    }

    @Test
    fun matchesCoverCandidatesWithDoubleSuffix() {
        val candidates = MediaMatcher.bestCandidates(
            "song.wav",
            listOf(file("song.wav.png"), file("cover.png"), file("song.bmp")),
            MediaMatcher.coverExtensions,
        )

        assertEquals(listOf("song.wav.png"), candidates.files.map { it.name })
    }

    @Test
    fun filtersByAllowedExtensions() {
        val candidates = MediaMatcher.bestCandidates(
            "song.mp3",
            listOf(file("song.gif"), file("song.txt"), file("song.docx")),
            MediaMatcher.coverExtensions,
        )

        assertNull(candidates.priority)
        assertTrue(candidates.files.isEmpty())
    }

    @Test
    fun allowsTxtAsLyricCandidate() {
        val candidates = MediaMatcher.bestCandidates(
            "song.mp3",
            listOf(file("song.txt")),
            MediaMatcher.lyricExtensions,
        )

        assertEquals(MediaMatcher.Priority.EXACT, candidates.priority)
    }

    @Test
    fun returnsNothingForUnrelatedNames() {
        val candidates = MediaMatcher.bestCandidates(
            "song.mp3",
            listOf(file("different.lrc"), file("another.png")),
            MediaMatcher.lyricExtensions,
        )

        assertTrue(candidates.files.isEmpty())
    }

    @Test
    fun sortsTiedCandidatesByName() {
        val candidates = MediaMatcher.bestCandidates(
            "song.mp3",
            listOf(file("song.vtt"), file("song.lrc")),
            MediaMatcher.lyricExtensions,
        )

        assertEquals(listOf("song.lrc", "song.vtt"), candidates.files.map { it.name })
    }
}
