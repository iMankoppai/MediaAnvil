package com.imankoppai.mediaanvil.tools

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioRenamerTest {
    private fun fields(
        name: String,
        artist: String = "",
        title: String = "",
        album: String = "",
        track: String = "",
        year: String = "",
    ) = AudioRenamer.Fields(name, artist, title, album, track, year)

    @Test
    fun rendersTemplateAndKeepsExtension() {
        val name = AudioRenamer.renderName(
            "{artist} - {title}",
            fields("01 old.wav", artist = "Astra", title = "Midnight"),
            fallbackMissing = false,
        )
        assertEquals("Astra - Midnight.wav", name)
    }

    @Test
    fun formatsTrackNumbersAndYears() {
        assertEquals("07", AudioRenamer.normalizeTrack("7"))
        assertEquals("03", AudioRenamer.normalizeTrack("03/12"))
        assertEquals("", AudioRenamer.normalizeTrack("no digits"))
        assertEquals("2021", AudioRenamer.normalizeYear("released in 2021!"))
    }

    @Test
    fun sanitizesIllegalFilenameCharacters() {
        assertEquals("a b c", AudioRenamer.sanitizeFilename("a<b>:c?"))
        assertEquals("stem", AudioRenamer.sanitizeFilename(" stem. "))
    }

    @Test
    fun missingFieldsThrowWithoutFallback() {
        assertThrows(IllegalArgumentException::class.java) {
            AudioRenamer.renderName("{artist} - {title}", fields("old.mp3"), fallbackMissing = false)
        }
    }

    @Test
    fun fallbackSubstitutesOriginalStem() {
        val name = AudioRenamer.renderName(
            "{artist} - {title}",
            fields("old song.mp3"),
            fallbackMissing = true,
        )
        assertEquals("old song - old song.mp3", name)
    }

    @Test
    fun unknownTemplateFieldsAreRejected() {
        assertThrows(IllegalArgumentException::class.java) {
            AudioRenamer.validateTemplate("{naughty}")
        }
        assertThrows(IllegalArgumentException::class.java) {
            AudioRenamer.validateTemplate("   ")
        }
        assertEquals(setOf("artist", "title"), AudioRenamer.validateTemplate("{title} by {artist}"))
    }

    @Test
    fun marksIdenticalNamesAsNoChange() {
        val plan = AudioRenamer.buildPlan(
            listOf(fields("Astra - Midnight.flac", artist = "Astra", title = "Midnight")),
            "{artist} - {title}",
            fallbackMissing = false,
        )
        assertEquals(AudioRenamer.Status.NO_CHANGE, plan.single().status)
    }

    @Test
    fun flagsDuplicateTargetsAsConflicts() {
        val plan = AudioRenamer.buildPlan(
            listOf(
                fields("one.mp3", artist = "A", title = "Same"),
                fields("two.mp3", artist = "B", title = "Same"),
            ),
            "{title}",
            fallbackMissing = false,
        )
        assertTrue(plan.all { it.status == AudioRenamer.Status.CONFLICT })
        assertTrue(plan.none { it.canRename })
    }

    @Test
    fun avoidsExistingFilesWithSuffix() {
        val plan = AudioRenamer.buildPlan(
            listOf(fields("song.mp3", artist = "Astra", title = "Midnight")),
            "{artist} - {title}",
            fallbackMissing = false,
            existingNames = setOf("astra - midnight.mp3"),
        )
        val item = plan.single()
        assertEquals(AudioRenamer.Status.READY_AVOIDED, item.status)
        assertEquals("Astra - Midnight_1.mp3", item.newName)
    }

    @Test
    fun treatsCaseOnlyDifferenceAsNoChange() {
        val plan = AudioRenamer.buildPlan(
            listOf(fields("astra - midnight.flac", artist = "Astra", title = "Midnight")),
            "{artist} - {title}",
            fallbackMissing = false,
        )
        assertEquals(AudioRenamer.Status.NO_CHANGE, plan.single().status)
    }
}
