package com.imankoppai.mediaanvil.data

import android.content.Context
import android.net.Uri
import com.imankoppai.mediaanvil.model.TrackGroup
import org.json.JSONArray
import org.json.JSONObject

class PlaybackPreferences(context: Context) {
    private val preferences = context.getSharedPreferences("mediaanvil_playback", Context.MODE_PRIVATE)

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

    var playbackSpeed: Float
        get() = preferences.getFloat("playback_speed", 1f)
        set(value) {
            preferences.edit().putFloat("playback_speed", value).apply()
        }

    var seekBackSeconds: Int
        get() = preferences.getInt("seek_back_seconds", 5).coerceIn(1, 300)
        set(value) {
            preferences.edit().putInt("seek_back_seconds", value.coerceIn(1, 300)).apply()
        }

    var seekForwardSeconds: Int
        get() = preferences.getInt("seek_forward_seconds", 30).coerceIn(1, 300)
        set(value) {
            preferences.edit().putInt("seek_forward_seconds", value.coerceIn(1, 300)).apply()
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

    /** Sleep timer waits for the current track to finish before pausing. */
    var sleepFinishTrack: Boolean
        get() = preferences.getBoolean("sleep_finish_track", false)
        set(value) {
            preferences.edit().putBoolean("sleep_finish_track", value).apply()
        }

    /** Show each lyric line's timestamp above the text. */
    var showLyricsTimestamps: Boolean
        get() = preferences.getBoolean("show_lyrics_timestamps", false)
        set(value) {
            preferences.edit().putBoolean("show_lyrics_timestamps", value).apply()
        }

    /** Sleep timer closes the app when it fires. */
    var sleepCloseApp: Boolean
        get() = preferences.getBoolean("sleep_close_app", false)
        set(value) {
            preferences.edit().putBoolean("sleep_close_app", value).apply()
        }

    /** "all" imports every supported audio file; "folders" only imports scanFolders. */
    var libraryScanMode: String
        get() = preferences.getString("library_scan_mode", "all") ?: "all"
        set(value) {
            preferences.edit().putString("library_scan_mode", value).apply()
        }

    /** Relative folder paths (trailing slash) that are scanned in "folders" mode. */
    var scanFolders: Set<String>
        get() = preferences.getStringSet("scan_folders", emptySet())?.toSet() ?: emptySet()
        set(value) {
            preferences.edit().putStringSet("scan_folders", value).apply()
        }

    /** Epoch-ms of the last automatic update check, throttling it to once a day. */
    var updateLastCheckAt: Long
        get() = preferences.getLong("update_last_check_at", 0L)
        set(value) {
            preferences.edit().putLong("update_last_check_at", value).apply()
        }

    /** "fileName", "title" or "duration". */
    var librarySort: String
        get() = preferences.getString("library_sort", "fileName") ?: "fileName"
        set(value) {
            preferences.edit().putString("library_sort", value).apply()
        }

    /** User-created local groups containing stable SAF document URIs. */
    var trackGroups: List<TrackGroup>
        get() {
            val raw = preferences.getString("track_groups", null) ?: return emptyList()
            return runCatching {
                val array = org.json.JSONArray(raw)
                List(array.length()) { index ->
                    val item = array.getJSONObject(index)
                    val uris = item.optJSONArray("trackUris") ?: org.json.JSONArray()
                    TrackGroup(
                        id = item.getString("id"),
                        name = item.getString("name"),
                        trackUris = buildSet {
                            for (uriIndex in 0 until uris.length()) add(uris.getString(uriIndex))
                        },
                    )
                }
            }.getOrDefault(emptyList())
        }
        set(value) {
            val array = org.json.JSONArray()
            value.forEach { group ->
                array.put(
                    org.json.JSONObject()
                        .put("id", group.id)
                        .put("name", group.name)
                        .put("trackUris", org.json.JSONArray(group.trackUris.toList())),
                )
            }
            preferences.edit().putString("track_groups", array.toString()).apply()
        }

    /** Tracks hidden from the player library; the underlying documents are untouched. */
    var hiddenTrackUris: Set<String>
        get() = preferences.getStringSet("hidden_track_uris", emptySet())?.toSet() ?: emptySet()
        set(value) {
            preferences.edit().putStringSet("hidden_track_uris", value.toSet()).apply()
        }

    /** Theme mode: "" = follow system, "light", "dark". */
    var themeMode: String
        get() = preferences.getString("theme_mode", "") ?: ""
        set(value) {
            preferences.edit().putString("theme_mode", value).apply()
        }

    /** Media button double press action: "" = next track, "previous" or "none". */
    var doublePressAction: String
        get() = when (val saved = preferences.getString("double_press_action", "") ?: "") {
            "none" -> "pause"
            "", "previous", "pause" -> saved
            else -> ""
        }
        set(value) {
            preferences.edit().putString("double_press_action", value).apply()
        }

    fun customCoverFor(trackUri: Uri): Uri? {
        val raw = preferences.getString("custom_covers", null) ?: return null
        return runCatching {
            org.json.JSONObject(raw).optString(trackUri.toString())
                .takeIf(String::isNotEmpty)
                ?.let(Uri::parse)
        }.getOrNull()
    }

    fun setCustomCover(trackUri: Uri, coverUri: Uri) {
        val covers = runCatching {
            org.json.JSONObject(preferences.getString("custom_covers", null) ?: "{}")
        }.getOrElse { org.json.JSONObject() }
        covers.put(trackUri.toString(), coverUri.toString())
        preferences.edit().putString("custom_covers", covers.toString()).apply()
    }

    fun lyricsOffsetFor(trackUri: Uri): Long = runCatching {
        JSONObject(preferences.getString("lyrics_offsets", null) ?: "{}")
            .optLong(trackUri.toString(), 0L)
            .coerceIn(-60_000L, 60_000L)
    }.getOrDefault(0L)

    fun setLyricsOffset(trackUri: Uri, offsetMs: Long) {
        val offsets = runCatching {
            JSONObject(preferences.getString("lyrics_offsets", null) ?: "{}")
        }.getOrElse { JSONObject() }
        val value = offsetMs.coerceIn(-60_000L, 60_000L)
        if (value == 0L) offsets.remove(trackUri.toString()) else offsets.put(trackUri.toString(), value)
        preferences.edit().putString("lyrics_offsets", offsets.toString()).apply()
    }

    internal fun customCoversJson(): JSONObject = runCatching {
        JSONObject(preferences.getString("custom_covers", null) ?: "{}")
    }.getOrElse { JSONObject() }

    internal fun lyricsOffsetsJson(): JSONObject = runCatching {
        JSONObject(preferences.getString("lyrics_offsets", null) ?: "{}")
    }.getOrElse { JSONObject() }

    internal fun restoreFromBackup(root: JSONObject) {
        val settings = root.getJSONObject("settings")
        val groupsJson = root.getJSONArray("groups")
        val restoredGroups = List(groupsJson.length()) { index ->
            val item = groupsJson.getJSONObject(index)
            val uris = item.optJSONArray("trackUris") ?: JSONArray()
            TrackGroup(
                id = item.getString("id"),
                name = item.getString("name"),
                trackUris = buildSet {
                    for (uriIndex in 0 until uris.length()) add(uris.getString(uriIndex))
                },
            )
        }
        val hidden = root.optJSONArray("hiddenTrackUris") ?: JSONArray()
        val covers = root.optJSONObject("customCovers") ?: JSONObject()
        val offsets = root.optJSONObject("lyricsOffsets") ?: JSONObject()

        preferences.edit()
            .putString("language", settings.optString("language", ""))
            .putBoolean("auto_load_lyrics", settings.optBoolean("autoLoadLyrics", true))
            .putFloat("playback_speed", settings.optDouble("playbackSpeed", 1.0).toFloat().coerceIn(0.25f, 3f))
            .putInt("seek_back_seconds", settings.optInt("seekBackSeconds", 5).coerceIn(1, 300))
            .putInt("seek_forward_seconds", settings.optInt("seekForwardSeconds", 30).coerceIn(1, 300))
            .putBoolean("shuffle_enabled", settings.optBoolean("shuffleEnabled", false))
            .putInt("repeat_mode", settings.optInt("repeatMode", 0))
            .putString("library_sort", settings.optString("librarySort", "fileName"))
            .putString("theme_mode", settings.optString("themeMode", ""))
            .putString("double_press_action", settings.optString("doublePressAction", ""))
            .putString("track_groups", JSONArray().apply {
                restoredGroups.forEach { group ->
                    put(JSONObject()
                        .put("id", group.id)
                        .put("name", group.name)
                        .put("trackUris", JSONArray(group.trackUris.toList())))
                }
            }.toString())
            .putStringSet("hidden_track_uris", buildSet {
                for (index in 0 until hidden.length()) add(hidden.getString(index))
            })
            .putString("custom_covers", covers.toString())
            .putString("lyrics_offsets", offsets.toString())
            .commit()
    }

}
