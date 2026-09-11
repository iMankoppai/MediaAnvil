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

    /** Default tag-save mode, mirroring the desktop setting; false = save as. */
    var defaultOverwrite: Boolean
        get() = preferences.getBoolean("default_overwrite", false)
        set(value) {
            preferences.edit().putBoolean("default_overwrite", value).apply()
        }

    /** "", "zh-CN" or "en"; empty follows the system language. */
    var language: String
        get() = preferences.getString("language", "") ?: ""
        set(value) {
            preferences.edit().putString("language", value).apply()
        }

    var autoLoadLyrics: Boolean
        get() = preferences.getBoolean("auto_load_lyrics", true)
        set(value) {
            preferences.edit().putBoolean("auto_load_lyrics", value).apply()
        }

    /** LRC final-line duration in seconds, mirroring the desktop setting. */
    var lrcTailSeconds: Int
        get() = preferences.getInt("lrc_tail_seconds", 5)
        set(value) {
            preferences.edit().putInt("lrc_tail_seconds", value.coerceIn(1, 15)).apply()
        }

    var includeSubfolders: Boolean
        get() = preferences.getBoolean("include_subfolders", true)
        set(value) {
            preferences.edit().putBoolean("include_subfolders", value).apply()
        }

    var audioConvertTarget: String
        get() = preferences.getString("audio_convert_target", "m4a") ?: "m4a"
        set(value) {
            preferences.edit().putString("audio_convert_target", value).apply()
        }

    var imageConvertTarget: String
        get() = preferences.getString("image_convert_target", "jpg") ?: "jpg"
        set(value) {
            preferences.edit().putString("image_convert_target", value).apply()
        }

    var imageQuality: Int
        get() = preferences.getInt("image_quality", 90)
        set(value) {
            preferences.edit().putInt("image_quality", value.coerceIn(1, 100)).apply()
        }
}
