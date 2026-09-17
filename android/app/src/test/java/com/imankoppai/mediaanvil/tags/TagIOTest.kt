package com.imankoppai.mediaanvil.tags

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeFalse
import org.junit.Test
import org.jaudiotagger.audio.AudioFileIO
import org.jaudiotagger.audio.mp3.MP3File
import org.jaudiotagger.tag.FieldKey
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

class TagIOTest {
    @Test
    fun supportedContainersAreWritable() {
        listOf("track.mp3", "track.wav", "track.FLAC", "track.m4a", "track.ogg", "track.opus")
            .forEach { assertTrue(it, TagIO.isWritable(it)) }
    }

    @Test
    fun rawAacAndUnknownFilesRemainReadOnly() {
        listOf("track.aac", "track", "track.txt")
            .forEach { assertFalse(it, TagIO.isWritable(it)) }
    }

    @Test
    fun wavRoundTripPreservesAudioAndOtherInfoFields() {
        val file = File.createTempFile("mediaanvil-tags", ".wav").apply {
            deleteOnExit()
            writeBytes(testWave())
        }
        val originalAudio = chunkData(file.readBytes(), "data")

        TagIO.write(file, "测试标题", "青葉りんご")

        assertEquals(TagIO.Tags("测试标题", "青葉りんご"), TagIO.read(file))
        file.inputStream().use {
            assertEquals(WavInfoTagIO.Tags("测试标题", "青葉りんご"), WavInfoTagIO.read(it))
        }
        assertArrayEquals(originalAudio, chunkData(file.readBytes(), "data"))
        assertTrue(file.readBytes().toString(Charsets.ISO_8859_1).contains("IPRD"))

        TagIO.write(file, "第二标题", "")
        assertEquals(TagIO.Tags("第二标题", ""), TagIO.read(file))
        assertArrayEquals(originalAudio, chunkData(file.readBytes(), "data"))
    }

    @Test
    fun legacyMp3IsMigratedToUnicodeId3v23WithoutLosingBasicFields() {
        val file = resourceCopy("tag-fixtures/id3v1-base.mp3", ".mp3")
        appendId3v1(file)
        val before = AudioFileIO.read(file) as MP3File
        assertTrue(before.hasID3v1Tag())
        assertFalse(before.hasID3v2Tag())

        TagIO.write(file, "中文歌名", "青葉りんご")

        val after = AudioFileIO.read(file) as MP3File
        assertTrue(after.hasID3v2Tag())
        assertEquals("中文歌名", after.tag.getFirst(FieldKey.TITLE))
        assertEquals("青葉りんご", after.tag.getFirst(FieldKey.ARTIST))
        assertEquals("KeepAlbum", after.tag.getFirst(FieldKey.ALBUM))
        assertEquals("2023", after.tag.getFirst(FieldKey.YEAR))
        assertEquals("7", after.tag.getFirst(FieldKey.TRACK))
    }

    @Test
    fun flacUnicodeRoundTripPreservesOtherTags() = verifyUnicodeRoundTrip("flac")

    @Test
    fun m4aUnicodeRoundTripPreservesOtherTags() {
        // jAudioTagger keeps the MP4 input handle open on Windows, where an open file cannot
        // be renamed during commit. Android allows that replacement and is covered on-device.
        assumeFalse(System.getProperty("os.name").orEmpty().startsWith("Windows", ignoreCase = true))
        verifyUnicodeRoundTrip("m4a")
    }

    @Test
    fun oggUnicodeRoundTripPreservesOtherTags() = verifyUnicodeRoundTrip("ogg")

    @Test
    fun opusUnicodeRoundTripPreservesOtherTags() = verifyUnicodeRoundTrip("opus")

    private fun verifyUnicodeRoundTrip(extension: String) {
        val file = resourceCopy("tag-fixtures/tags.$extension", ".$extension")

        TagIO.write(file, "中文歌名", "青葉りんご")

        assertEquals(TagIO.Tags("中文歌名", "青葉りんご"), TagIO.read(file))
        assertEquals("KeepAlbum", AudioFileIO.read(file).tag.getFirst(FieldKey.ALBUM))
    }

    private fun resourceCopy(name: String, suffix: String): File {
        val directory = File("build/tag-test-tmp").apply { mkdirs() }
        val target = File.createTempFile("mediaanvil-tags", suffix, directory).apply { deleteOnExit() }
        javaClass.classLoader!!.getResourceAsStream(name)!!.use { input ->
            target.outputStream().use { output -> input.copyTo(output) }
        }
        return target
    }

    private fun appendId3v1(file: File) {
        val tag = ByteArray(128)
        fun put(offset: Int, length: Int, value: String) {
            val encoded = value.toByteArray(Charsets.ISO_8859_1)
            encoded.copyInto(tag, destinationOffset = offset, endIndex = minOf(length, encoded.size))
        }
        put(0, 3, "TAG")
        put(3, 30, "LegacyTitle")
        put(33, 30, "LegacyArtist")
        put(63, 30, "KeepAlbum")
        put(93, 4, "2023")
        tag[125] = 0
        tag[126] = 7
        tag[127] = 0xFF.toByte()
        file.appendBytes(tag)
    }

    private fun testWave(): ByteArray {
        val body = ByteArrayOutputStream()
        body.write("WAVE".toByteArray(Charsets.US_ASCII))
        writeChunk(
            body,
            "fmt ",
            ByteBuffer.allocate(16).order(ByteOrder.LITTLE_ENDIAN)
                .putShort(1.toShort()).putShort(1.toShort()).putInt(8_000).putInt(16_000)
                .putShort(2.toShort()).putShort(16.toShort())
                .array(),
        )
        val info = ByteArrayOutputStream().apply {
            write("INFO".toByteArray(Charsets.US_ASCII))
            writeChunk(this, "IPRD", "保留专辑\u0000".toByteArray(Charsets.UTF_8))
        }.toByteArray()
        writeChunk(body, "LIST", info)
        writeChunk(body, "data", byteArrayOf(0, 1, 2, 3, 4, 5, 6, 7))
        return ByteArrayOutputStream().apply {
            write("RIFF".toByteArray(Charsets.US_ASCII))
            writeLe32(body.size().toLong())
            write(body.toByteArray())
        }.toByteArray()
    }

    private fun writeChunk(output: ByteArrayOutputStream, id: String, data: ByteArray) {
        output.write(id.toByteArray(Charsets.US_ASCII))
        output.writeLe32(data.size.toLong())
        output.write(data)
        if ((data.size and 1) == 1) output.write(0)
    }

    private fun ByteArrayOutputStream.writeLe32(value: Long) {
        write((value and 0xFF).toInt())
        write((value shr 8 and 0xFF).toInt())
        write((value shr 16 and 0xFF).toInt())
        write((value shr 24 and 0xFF).toInt())
    }

    private fun chunkData(wave: ByteArray, wanted: String): ByteArray {
        var position = 12
        while (position + 8 <= wave.size) {
            val id = String(wave, position, 4, Charsets.US_ASCII)
            val size = ByteBuffer.wrap(wave, position + 4, 4).order(ByteOrder.LITTLE_ENDIAN).int
            if (id == wanted) return wave.copyOfRange(position + 8, position + 8 + size)
            position += 8 + size + (size and 1)
        }
        error("missing_chunk_$wanted")
    }
}
