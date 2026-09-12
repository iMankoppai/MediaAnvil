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

    var playbackSpeed: Float
        get() = preferences.getFloat("playback_speed", 1f)
        set(value) {
            preferences.edit().putFloat("playback_speed", value).apply()
        }

    var shuffleEnabled: Boolean
        get() = preferences.getBoolean("shuffle_enabled", false)
        set(value) {
            preferences.edit().putBoolean("shuffle_enabled", value).apply()
        }

    var repeatMode: Int
        get() = preferences.getInt("repeat_mode", 0)
        set(value) {
            preferences.edit().putInt("repeat_mode", value).apply()
        }

    /** "fileName", "title" or "duration". */
    var librarySort: String
        get() = preferences.getString("library_sort", "fileName") ?: "fileName"
        set(value) {
            preferences.edit().putString("library_sort", value).apply()
        }

    /** Favourite track URIs (string forms). */
    var favorites: Set<String>
        get() = preferences.getStringSet("favorites", emptySet()) ?: emptySet()
        set(value) {
            preferences.edit().putStringSet("favorites", value).apply()
        }

    /** Recently played track URIs, newest first; the caller caps the length. */
    var recentUris: List<String>
        get() {
            val raw = preferences.getString("recent_uris", null) ?: return emptyList()
            return runCatching {
                val array = org.json.JSONArray(raw)
                List(array.length()) { array.getString(it) }
            }.getOrDefault(emptyList())
        }
        set(value) {
            preferences.edit().putString("recent_uris", org.json.JSONArray(value).toString()).apply()
        }

    /** Equalizer state; the Equalizer itself lives in the playback service process. */
    var eqEnabled: Boolean
        get() = preferences.getBoolean("eq_enabled", false)
        set(value) {
            preferences.edit().putBoolean("eq_enabled", value).apply()
        }

    var eqPreset: Int
        get() = preferences.getInt("eq_preset", 0)
        set(value) {
            preferences.edit().putInt("eq_preset", value).apply()
        }

    /** Theme mode: "" = follow system, "light", "dark". */
    var themeMode: String
        get() = preferences.getString("theme_mode", "") ?: ""
        set(value) {
            preferences.edit().putString("theme_mode", value).apply()
        }

    /** Material You wallpaper-derived colors (Android 12+). */
    var useDynamicColor: Boolean
        get() = preferences.getBoolean("use_dynamic_color", false)
        set(value) {
            preferences.edit().putBoolean("use_dynamic_color", value).apply()
        }

    /** Seed the palette from the playing track's cover art. */
    var useCoverColor: Boolean
        get() = preferences.getBoolean("use_cover_color", false)
        set(value) {
            preferences.edit().putBoolean("use_cover_color", value).apply()
        }

    /** Loudness boost in dB (0 = off, up to +15). */
    var loudnessGainDb: Int
        get() = preferences.getInt("loudness_gain_db", 0)
        set(value) {
            preferences.edit().putInt("loudness_gain_db", value).apply()
        }

    /** Audio conversion AAC bitrate in kbps (128/192/256). */
    var audioConvertBitrateKbps: Int
        get() = preferences.getInt("audio_convert_bitrate_kbps", 192)
        set(value) {
            preferences.edit().putInt("audio_convert_bitrate_kbps", value).apply()
        }

    /** Media button double press action: "" = next track, "previous", "speed", "none". */
    var doublePressAction: String
        get() = preferences.getString("double_press_action", "") ?: ""
        set(value) {
            preferences.edit().putString("double_press_action", value).apply()
        }

    /** Authorized library roots; empty means fall back to [lastFolder]. */
    var folders: List<android.net.Uri>
        get() {
            val raw = preferences.getString("library_folders", null) ?: return emptyList()
            return runCatching {
                val array = org.json.JSONArray(raw)
                List(array.length()) { android.net.Uri.parse(array.getString(it)) }
            }.getOrDefault(emptyList())
        }
        set(value) {
            val array = org.json.JSONArray()
            value.forEach { array.put(it.toString()) }
            preferences.edit().putString("library_folders", array.toString()).apply()
        }
}
