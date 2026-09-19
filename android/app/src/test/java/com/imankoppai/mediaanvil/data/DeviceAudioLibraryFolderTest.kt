package com.imankoppai.mediaanvil.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DeviceAudioLibraryFolderTest {
    private val root = "/storage/emulated/0"

    @Test
    fun `relativeFolder strips the storage root and keeps a trailing slash`() {
        assertEquals("Music/", DeviceAudioLibrary.relativeFolder("$root/Music", root))
        assertEquals("Music/sub/", DeviceAudioLibrary.relativeFolder("$root/Music/sub", root))
        assertEquals("Music/", DeviceAudioLibrary.relativeFolder("$root/Music/", root))
    }

    @Test
    fun `relativeFolder keeps paths outside the primary root intact`() {
        assertEquals("34FE-19F0/Music/", DeviceAudioLibrary.relativeFolder("/storage/34FE-19F0/Music", root))
        assertEquals("/", DeviceAudioLibrary.relativeFolder("", root))
    }

    @Test
    fun `empty folder set allows everything`() {
        assertTrue(DeviceAudioLibrary.isFolderAllowed("$root/Recordings/call.m4a", emptySet(), root))
        assertTrue(DeviceAudioLibrary.isFolderAllowed("", emptySet(), root))
    }

    @Test
    fun `selected folders include their subfolders`() {
        val folders = setOf("Music/")
        assertTrue(DeviceAudioLibrary.isFolderAllowed("$root/Music", folders, root))
        assertTrue(DeviceAudioLibrary.isFolderAllowed("$root/Music/", folders, root))
        assertTrue(DeviceAudioLibrary.isFolderAllowed("$root/Music/sub", folders, root))
        assertFalse(DeviceAudioLibrary.isFolderAllowed("$root/Recordings", folders, root))
        assertFalse(DeviceAudioLibrary.isFolderAllowed("", folders, root))
    }

    @Test
    fun `tree document ids convert to relative folders`() {
        assertEquals("Music/sub/", DeviceAudioLibrary.treeDocumentIdToRelativeFolder("primary:Music/sub"))
        assertEquals("Music/", DeviceAudioLibrary.treeDocumentIdToRelativeFolder("primary:Music"))
        assertEquals("34FE-19F0/Music/", DeviceAudioLibrary.treeDocumentIdToRelativeFolder("34FE-19F0:Music"))
        assertEquals(null, DeviceAudioLibrary.treeDocumentIdToRelativeFolder("primary:"))
    }

    @Test
    fun `similarly named folders do not match by prefix`() {
        val folders = setOf("Music/")
        assertFalse(DeviceAudioLibrary.isFolderAllowed("$root/MusicVideos", folders, root))
        assertTrue(DeviceAudioLibrary.isFolderAllowed("$root/MusicVideos", setOf("MusicVideos/"), root))
    }
}
