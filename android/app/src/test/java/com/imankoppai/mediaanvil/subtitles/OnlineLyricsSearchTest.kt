package com.imankoppai.mediaanvil.subtitles

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class OnlineLyricsSearchTest {
    @Test
    fun stripsCommonLocalizedAndEnglishVersionSuffixes() {
        assertEquals("稻香", OnlineLyricsClient.stripVersionQualifier("稻香（英文版）"))
        assertEquals("Song", OnlineLyricsClient.stripVersionQualifier("Song (Live Version)"))
        assertEquals("Song", OnlineLyricsClient.stripVersionQualifier("Song - Remix"))
    }

    @Test
    fun searchFallsBackFromExactToSimplifiedAndTitleOnly() {
        val queries = OnlineLyricsClient.searchQueries("稻香（英文版）", "DEER迪迩")

        assertEquals(3, queries.size)
        assertEquals("稻香（英文版）", queries[0].title)
        assertFalse(queries[0].relaxed)
        assertEquals("稻香", queries[1].title)
        assertEquals("DEER迪迩", queries[1].artist)
        assertTrue(queries[1].relaxed)
        assertEquals("稻香", queries[2].title)
        assertNull(queries[2].artist)
        assertTrue(queries[2].relaxed)
    }
}
