package com.imankoppai.mediaanvil.data

import android.content.Context
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject

object PlayerDataBackup {
    private const val SCHEMA_VERSION = 1

    fun export(context: Context, destination: Uri, preferences: PlaybackPreferences) {
        val output = JSONObject()
            .put("schemaVersion", SCHEMA_VERSION)
            .put("createdAt", System.currentTimeMillis())
            .put("settings", JSONObject()
                .put("language", preferences.language)
                .put("autoLoadLyrics", preferences.autoLoadLyrics)
                .put("playbackSpeed", preferences.playbackSpeed.toDouble())
                .put("seekBackSeconds", preferences.seekBackSeconds)
                .put("seekForwardSeconds", preferences.seekForwardSeconds)
                .put("shuffleEnabled", preferences.shuffleEnabled)
                .put("repeatMode", preferences.repeatMode)
                .put("librarySort", preferences.librarySort)
                .put("themeMode", preferences.themeMode)
                .put("doublePressAction", preferences.doublePressAction))
            .put("groups", JSONArray().apply {
                preferences.trackGroups.forEach { group ->
                    put(JSONObject()
                        .put("id", group.id)
                        .put("name", group.name)
                        .put("trackUris", JSONArray(group.trackUris.toList())))
                }
            })
            .put("hiddenTrackUris", JSONArray(preferences.hiddenTrackUris.toList()))
            .put("customCovers", preferences.customCoversJson())
            .put("lyricsOffsets", preferences.lyricsOffsetsJson())

        checkNotNull(context.contentResolver.openOutputStream(destination, "wt")).use { stream ->
            stream.writer(Charsets.UTF_8).use { it.write(output.toString(2)) }
        }
    }

    fun import(context: Context, source: Uri, preferences: PlaybackPreferences) {
        val raw = checkNotNull(context.contentResolver.openInputStream(source)).use { stream ->
            stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        }
        preferences.restoreFromBackup(JSONObject(raw).also { root ->
            check(root.optInt("schemaVersion", -1) == SCHEMA_VERSION) { "unsupported_schema" }
            check(root.has("settings") && root.has("groups")) { "invalid_backup" }
        })
    }
}
