package com.imankoppai.mediaanvil.data

import android.net.Uri
import com.imankoppai.mediaanvil.model.AudioTrack

data class ScannedFile(val uri: Uri, val name: String, val parentPath: String)

data class LibraryScan(val tracks: List<AudioTrack>, val files: List<ScannedFile>)
