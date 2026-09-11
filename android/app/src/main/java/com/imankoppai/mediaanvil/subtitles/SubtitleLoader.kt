package com.imankoppai.mediaanvil.subtitles

import android.content.Context
import android.net.Uri
import com.imankoppai.mediaanvil.model.SubtitleCue
import java.nio.charset.Charset

object SubtitleLoader {
    fun load(context: Context, uri: Uri, extension: String): List<SubtitleCue> {
        val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return emptyList()
        val text = decode(bytes)
        return SubtitleParser.parse(text, extension)
    }

    internal fun decode(bytes: ByteArray): String {
        if (bytes.size >= 3 && bytes[0] == 0xEF.toByte() && bytes[1] == 0xBB.toByte() && bytes[2] == 0xBF.toByte()) {
            return bytes.copyOfRange(3, bytes.size).toString(Charsets.UTF_8)
        }
        if (bytes.size >= 2 && bytes[0] == 0xFF.toByte() && bytes[1] == 0xFE.toByte()) {
            return bytes.copyOfRange(2, bytes.size).toString(Charsets.UTF_16LE)
        }
        if (bytes.size >= 2 && bytes[0] == 0xFE.toByte() && bytes[1] == 0xFF.toByte()) {
            return bytes.copyOfRange(2, bytes.size).toString(Charsets.UTF_16BE)
        }
        val utf8 = bytes.toString(Charsets.UTF_8)
        return if ('\uFFFD' in utf8) bytes.toString(Charset.forName("GB18030")) else utf8
    }
}
