package com.imankoppai.mediaanvil.tags

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Opus tag editing through the Kaned1as jaudiotagger fork (JitPack). */
class TagIOOpusTest {
    private fun resourceCopy(): File {
        val stream = javaClass.classLoader!!.getResourceAsStream("test.opus")!!
        val file = File.createTempFile("test", ".opus")
        file.deleteOnExit()
        file.outputStream().use { stream.copyTo(it) }
        return file
    }

    @Test
    fun opusReadsTags() {
        val snapshot = TagIO.readSnapshot(resourceCopy())
        assertEquals("Opus", snapshot.info.formatLabel)
        assertTrue(snapshot.writable)
    }

    @Test
    fun opusWriteReadRoundTrip() {
        val file = resourceCopy()
        TagIO.writeChanges(
            file,
            TagIO.TagChanges(
                title = "测试标题",
                artist = "测试艺术家",
                album = "测试专辑",
                lyricsLrc = "[00:01.00]hello world",
            ),
        )
        val after = TagIO.readSnapshot(file)
        assertEquals("测试标题", after.title)
        assertEquals("测试艺术家", after.artist)
        assertEquals("测试专辑", after.album)
        assertTrue(after.hasLyrics)
        assertTrue(after.lyrics.contains("hello world"))

        val png = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A) + ByteArray(64)
        TagIO.writeChanges(file, TagIO.TagChanges(coverData = png, coverMime = "image/png"))
        val withCover = TagIO.readSnapshot(file)
        assertTrue(withCover.hasCover)
    }
}
