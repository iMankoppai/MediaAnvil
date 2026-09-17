package com.imankoppai.mediaanvil.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class PlaybackSeekTest {
    @Test
    fun rewindStopsAtBeginning() {
        assertEquals(0L, seekBackTarget(currentMs = 3_000L, seconds = 5))
        assertEquals(5_000L, seekBackTarget(currentMs = 10_000L, seconds = 5))
    }

    @Test
    fun fastForwardStopsAtKnownDuration() {
        assertEquals(40_000L, seekForwardTarget(currentMs = 10_000L, durationMs = 60_000L, seconds = 30))
        assertEquals(60_000L, seekForwardTarget(currentMs = 50_000L, durationMs = 60_000L, seconds = 30))
    }

    @Test
    fun fastForwardWorksBeforeDurationIsKnown() {
        assertEquals(40_000L, seekForwardTarget(currentMs = 10_000L, durationMs = 0L, seconds = 30))
    }
}
