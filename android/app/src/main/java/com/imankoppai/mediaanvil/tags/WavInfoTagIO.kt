package com.imankoppai.mediaanvil.tags

import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.io.RandomAccessFile
import java.nio.charset.StandardCharsets

/** Minimal streaming RIFF/INFO title and artist reader/writer for standard WAV files. */
internal object WavInfoTagIO {
    private const val MAX_INFO_BYTES = 16 * 1024 * 1024L
    private const val UINT32_MAX = 0xFFFF_FFFFL

    data class Tags(val title: String?, val artist: String?)

    /** Read INFO tags from a content stream without copying the WAV data chunk. */
    fun read(input: InputStream): Tags {
        val header = ByteArray(12)
        input.readFully(header)
        check(header.fourCcAt(0) == "RIFF" && header.fourCcAt(8) == "WAVE") {
            "unsupported_wav_container"
        }
        var title: String? = null
        var artist: String? = null
        val chunkHeader = ByteArray(8)
        while (input.readChunkHeaderOrEof(chunkHeader)) {
            val id = chunkHeader.fourCcAt(0)
            val size = chunkHeader.uint32LeAt(4)
            if (id == "LIST" && size in 4L..MAX_INFO_BYTES) {
                val data = ByteArray(size.toInt())
                input.readFully(data)
                if (data.fourCcAt(0) == "INFO") {
                    val parsed = parseInfo(data)
                    if (title == null) title = parsed.title
                    if (artist == null) artist = parsed.artist
                }
            } else {
                input.skipFully(size)
            }
            if ((size and 1L) == 1L) input.skipFully(1L)
        }
        return Tags(title, artist)
    }

    fun read(file: File): Tags = RandomAccessFile(file, "r").use { input ->
        validateWave(input)
        var title: String? = null
        var artist: String? = null
        var position = 12L
        while (position + 8L <= input.length()) {
            input.seek(position)
            val id = input.readFourCc()
            val size = input.readUInt32Le()
            val dataStart = position + 8L
            val next = checkedChunkEnd(dataStart, size, input.length())
            if (id == "LIST" && size >= 4L && size <= MAX_INFO_BYTES) {
                input.seek(dataStart)
                if (input.readFourCc() == "INFO") {
                    val data = ByteArray(size.toInt())
                    input.seek(dataStart)
                    input.readFully(data)
                    val parsed = parseInfo(data)
                    if (title == null) title = parsed.title
                    if (artist == null) artist = parsed.artist
                }
            }
            position = next
        }
        Tags(title, artist)
    }

    fun write(file: File, title: String, artist: String) {
        val parent = requireNotNull(file.parentFile) { "missing_parent" }
        val temporary = File(parent, ".${file.name}.${System.nanoTime()}.wavtag")
        try {
            rewrite(file, temporary, title.trim(), artist.trim())
            temporary.inputStream().buffered().use { input ->
                file.outputStream().buffered().use { output -> input.copyTo(output) }
            }
            check(file.length() == temporary.length()) { "wav_replace_failed" }
        } finally {
            temporary.delete()
        }
    }

    private fun rewrite(source: File, target: File, title: String, artist: String) {
        RandomAccessFile(source, "r").use { input ->
            validateWave(input)
            target.outputStream().buffered().use { output ->
                input.seek(0L)
                val header = ByteArray(12)
                input.readFully(header)
                output.write(header)

                var position = 12L
                var wroteTags = false
                while (position + 8L <= input.length()) {
                    input.seek(position)
                    val id = input.readFourCc()
                    val size = input.readUInt32Le()
                    val dataStart = position + 8L
                    val next = checkedChunkEnd(dataStart, size, input.length())
                    if (id == "LIST" && size >= 4L) {
                        input.seek(dataStart)
                        val listType = input.readFourCc()
                        if (listType == "INFO") {
                            check(size <= MAX_INFO_BYTES) { "wav_info_too_large" }
                            val data = ByteArray(size.toInt())
                            input.seek(dataStart)
                            input.readFully(data)
                            writeChunk(
                                output,
                                "LIST",
                                rewriteInfo(data, title, artist, addEditedFields = !wroteTags),
                            )
                            wroteTags = true
                            position = next
                            continue
                        }
                    }
                    copyRange(input, output, position, next - position)
                    position = next
                }

                if (!wroteTags && (title.isNotEmpty() || artist.isNotEmpty())) {
                    writeChunk(output, "LIST", newInfo(title, artist))
                }
                if (position < input.length()) {
                    copyRange(input, output, position, input.length() - position)
                }
            }
        }

        RandomAccessFile(target, "rw").use { output ->
            val riffSize = output.length() - 8L
            check(riffSize in 0..UINT32_MAX) { "wav_too_large" }
            output.seek(4L)
            output.writeUInt32Le(riffSize)
        }
    }

    private fun validateWave(input: RandomAccessFile) {
        check(input.length() >= 12L) { "invalid_wav" }
        check(input.length() - 8L <= UINT32_MAX) { "wav_too_large" }
        input.seek(0L)
        check(input.readFourCc() == "RIFF") { "unsupported_wav_container" }
        input.readUInt32Le()
        check(input.readFourCc() == "WAVE") { "invalid_wav" }
    }

    private fun checkedChunkEnd(dataStart: Long, size: Long, fileLength: Long): Long {
        val dataEnd = dataStart + size
        check(dataEnd >= dataStart && dataEnd <= fileLength) { "invalid_wav_chunk" }
        val paddedEnd = dataEnd + (size and 1L)
        check(paddedEnd >= dataEnd && paddedEnd <= fileLength) { "invalid_wav_padding" }
        return paddedEnd
    }

    private fun parseInfo(data: ByteArray): Tags {
        check(data.size >= 4 && data.fourCcAt(0) == "INFO") { "invalid_wav_info" }
        var title: String? = null
        var artist: String? = null
        var position = 4
        while (position < data.size) {
            check(position + 8 <= data.size) { "invalid_wav_info" }
            val id = data.fourCcAt(position)
            val size = data.uint32LeAt(position + 4)
            check(size <= Int.MAX_VALUE.toLong()) { "invalid_wav_info" }
            val valueStart = position + 8
            val valueEndLong = valueStart.toLong() + size
            check(valueEndLong <= data.size.toLong()) { "invalid_wav_info" }
            val valueEnd = valueEndLong.toInt()
            when (id) {
                "INAM" -> if (title == null) title = decodeText(data.copyOfRange(valueStart, valueEnd))
                "IART" -> if (artist == null) artist = decodeText(data.copyOfRange(valueStart, valueEnd))
            }
            val next = valueEndLong + (size and 1L)
            check(next <= data.size.toLong()) { "invalid_wav_info" }
            position = next.toInt()
        }
        return Tags(title, artist)
    }

    private fun rewriteInfo(
        data: ByteArray,
        title: String,
        artist: String,
        addEditedFields: Boolean,
    ): ByteArray {
        check(data.size >= 4 && data.fourCcAt(0) == "INFO") { "invalid_wav_info" }
        val output = ByteArrayOutputStream(data.size + title.length + artist.length + 32)
        output.write("INFO".toByteArray(StandardCharsets.US_ASCII))
        var position = 4
        while (position < data.size) {
            check(position + 8 <= data.size) { "invalid_wav_info" }
            val id = data.fourCcAt(position)
            val size = data.uint32LeAt(position + 4)
            val valueEnd = position.toLong() + 8L + size
            val next = valueEnd + (size and 1L)
            check(next <= data.size.toLong()) { "invalid_wav_info" }
            if (id != "INAM" && id != "IART") {
                output.write(data, position, (next - position).toInt())
            }
            position = next.toInt()
        }
        if (addEditedFields) {
            writeInfoText(output, "INAM", title)
            writeInfoText(output, "IART", artist)
        }
        return output.toByteArray()
    }

    private fun newInfo(title: String, artist: String): ByteArray =
        ByteArrayOutputStream(title.length + artist.length + 36).also { output ->
            output.write("INFO".toByteArray(StandardCharsets.US_ASCII))
            writeInfoText(output, "INAM", title)
            writeInfoText(output, "IART", artist)
        }.toByteArray()

    private fun writeInfoText(output: OutputStream, id: String, value: String) {
        if (value.isEmpty()) return
        val encoded = value.toByteArray(StandardCharsets.UTF_8) + 0.toByte()
        writeChunk(output, id, encoded)
    }

    private fun writeChunk(output: OutputStream, id: String, data: ByteArray) {
        require(id.length == 4)
        output.write(id.toByteArray(StandardCharsets.US_ASCII))
        output.writeUInt32Le(data.size.toLong())
        output.write(data)
        if ((data.size and 1) == 1) output.write(0)
    }

    private fun copyRange(input: RandomAccessFile, output: OutputStream, start: Long, count: Long) {
        input.seek(start)
        var remaining = count
        val buffer = ByteArray(256 * 1024)
        while (remaining > 0L) {
            val read = input.read(buffer, 0, minOf(buffer.size.toLong(), remaining).toInt())
            check(read >= 0) { "unexpected_wav_eof" }
            output.write(buffer, 0, read)
            remaining -= read
        }
    }

    private fun decodeText(bytes: ByteArray): String {
        var end = bytes.size
        while (end > 0 && bytes[end - 1] == 0.toByte()) end--
        if (end == 0) return ""
        val start = if (end >= 3 && bytes[0] == 0xEF.toByte() && bytes[1] == 0xBB.toByte() &&
            bytes[2] == 0xBF.toByte()
        ) 3 else 0
        return String(bytes, start, end - start, StandardCharsets.UTF_8).trimEnd()
    }

    private fun InputStream.readChunkHeaderOrEof(buffer: ByteArray): Boolean {
        val first = read()
        if (first < 0) return false
        buffer[0] = first.toByte()
        var offset = 1
        while (offset < buffer.size) {
            val count = read(buffer, offset, buffer.size - offset)
            check(count > 0) { "unexpected_wav_eof" }
            offset += count
        }
        return true
    }

    private fun InputStream.readFully(buffer: ByteArray) {
        var offset = 0
        while (offset < buffer.size) {
            val count = read(buffer, offset, buffer.size - offset)
            check(count > 0) { "unexpected_wav_eof" }
            offset += count
        }
    }

    private fun InputStream.skipFully(count: Long) {
        var remaining = count
        val discard = ByteArray(64 * 1024)
        while (remaining > 0L) {
            val skipped = skip(remaining)
            if (skipped > 0L) {
                remaining -= skipped
            } else {
                val read = read(discard, 0, minOf(discard.size.toLong(), remaining).toInt())
                check(read > 0) { "unexpected_wav_eof" }
                remaining -= read
            }
        }
    }

    private fun RandomAccessFile.readFourCc(): String {
        val bytes = ByteArray(4)
        readFully(bytes)
        return String(bytes, StandardCharsets.US_ASCII)
    }

    private fun ByteArray.fourCcAt(offset: Int): String =
        String(this, offset, 4, StandardCharsets.US_ASCII)

    private fun RandomAccessFile.readUInt32Le(): Long {
        val b0 = readUnsignedByte().toLong()
        val b1 = readUnsignedByte().toLong()
        val b2 = readUnsignedByte().toLong()
        val b3 = readUnsignedByte().toLong()
        return b0 or (b1 shl 8) or (b2 shl 16) or (b3 shl 24)
    }

    private fun ByteArray.uint32LeAt(offset: Int): Long =
        (this[offset].toLong() and 0xFFL) or
            ((this[offset + 1].toLong() and 0xFFL) shl 8) or
            ((this[offset + 2].toLong() and 0xFFL) shl 16) or
            ((this[offset + 3].toLong() and 0xFFL) shl 24)

    private fun RandomAccessFile.writeUInt32Le(value: Long) {
        write((value and 0xFF).toInt())
        write((value shr 8 and 0xFF).toInt())
        write((value shr 16 and 0xFF).toInt())
        write((value shr 24 and 0xFF).toInt())
    }

    private fun OutputStream.writeUInt32Le(value: Long) {
        write((value and 0xFF).toInt())
        write((value shr 8 and 0xFF).toInt())
        write((value shr 16 and 0xFF).toInt())
        write((value shr 24 and 0xFF).toInt())
    }
}
