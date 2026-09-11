package com.imankoppai.mediaanvil.data

import android.content.Context
import android.net.Uri

class PlaybackPreferences(context: Context) {
    private val preferences = context.getSharedPreferences("mediaanvil_playback", Context.MODE_PRIVATE)

    var lastFolder: Uri?
        get() = preferences.getString("last_folder", null)?.let(Uri::parse)
        set(value) {
            preferences.edit().putString("last_folder", value?.toString()).apply()
        }

    fun position(uri: Uri): Long = preferences.getLong("position_${uri}", 0L)

    fun savePosition(uri: Uri, positionMs: Long) {
        preferences.edit().putLong("position_${uri}", positionMs.coerceAtLeast(0L)).apply()
    }

    var preferEmbeddedLyrics: Boolean
        get() = preferences.getBoolean("prefer_embedded_lyrics", false)
        set(value) {
            preferences.edit().putBoolean("prefer_embedded_lyrics", value).apply()
        }
}
