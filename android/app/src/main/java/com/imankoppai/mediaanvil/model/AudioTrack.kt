package com.imankoppai.mediaanvil.model

import android.net.Uri
import androidx.documentfile.provider.DocumentFile

data class AudioTrack(
    val uri: Uri,
    val fileName: String,
    val title: String,
    val artist: String?,
    val album: String?,
    val durationMs: Long,
    val subtitleUri: Uri?,
    val subtitleExtension: String?,
    val parent: DocumentFile? = null,
    val parentPath: String = "",
)

data class SubtitleCue(
    val startMs: Long,
    val endMs: Long,
    val text: String,
)
