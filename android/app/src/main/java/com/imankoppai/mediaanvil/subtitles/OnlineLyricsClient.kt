package com.imankoppai.mediaanvil.subtitles

import com.imankoppai.mediaanvil.model.AudioTrack
import org.json.JSONArray
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URLEncoder
import java.net.URL
import java.nio.charset.StandardCharsets
import kotlin.math.abs

data class OnlineLyricsCandidate(
    val id: Long,
    val trackName: String,
    val artistName: String,
    val albumName: String,
    val durationSeconds: Int,
    val syncedLyrics: String,
    val possibleMismatch: Boolean = false,
)

internal data class LyricsSearchQuery(val title: String, val artist: String?, val relaxed: Boolean)

/** Minimal read-only LRCLIB client. Downloaded lyrics are stored as sidecar LRC files. */
object OnlineLyricsClient {
    private const val ENDPOINT = "https://lrclib.net/api/search"
    private const val MAX_RESPONSE_BYTES = 4 * 1024 * 1024

    fun search(
        track: AudioTrack,
        queryTitle: String = track.title,
        queryArtist: String? = track.artist,
    ): List<OnlineLyricsCandidate> {
        var usedQuery = LyricsSearchQuery(queryTitle.trim(), queryArtist?.trim(), relaxed = false)
        var results = emptyList<OnlineLyricsCandidate>()
        for (query in searchQueries(queryTitle, queryArtist)) {
            usedQuery = query
            results = request(query.title, query.artist)
            if (results.isNotEmpty()) break
        }
        val wantedDuration = (track.durationMs / 1_000L).toInt()
        return results
            .distinctBy { it.id }
            .sortedWith(
                compareBy<OnlineLyricsCandidate> {
                    if (normalize(it.trackName) == normalize(usedQuery.title)) 0 else 1
                }.thenBy {
                    if (wantedDuration > 0 && it.durationSeconds > 0) abs(it.durationSeconds - wantedDuration) else Int.MAX_VALUE
                },
            )
            .map { candidate ->
                candidate.copy(
                    possibleMismatch = usedQuery.relaxed || candidateDoesNotMatch(track, candidate),
                )
            }
            .take(10)
    }

    internal fun searchQueries(title: String, artist: String?): List<LyricsSearchQuery> {
        val exactTitle = title.trim()
        if (exactTitle.isEmpty()) return emptyList()
        val cleanArtist = artist?.trim()?.takeIf(String::isNotEmpty)
        val simplified = stripVersionQualifier(
            exactTitle.replace(Regex("^\\s*\\d+[._ -]+"), "").trim(),
        ).ifEmpty { exactTitle }
        return listOf(
            LyricsSearchQuery(exactTitle, cleanArtist, relaxed = false),
            LyricsSearchQuery(simplified, cleanArtist, relaxed = simplified != exactTitle),
            LyricsSearchQuery(simplified, null, relaxed = cleanArtist != null || simplified != exactTitle),
        ).distinctBy { "${it.title.lowercase()}\u0000${it.artist?.lowercase().orEmpty()}" }
    }

    internal fun stripVersionQualifier(title: String): String {
        val qualifier = "英文版|中文版|日文版|韩文版|英语版|国语版|翻唱|重制版|现场版|纯音乐|伴奏|cover|version|live|remix|remaster(?:ed)?"
        return title
            .replace(
                Regex("\\s*[（(\\[【][^）)\\]】]*(?:$qualifier)[^）)\\]】]*[）)\\]】]\\s*$", RegexOption.IGNORE_CASE),
                "",
            )
            .replace(Regex("\\s*[-–—_]\\s*(?:$qualifier)\\s*$", RegexOption.IGNORE_CASE), "")
            .trim()
    }

    private fun request(title: String, artist: String?): List<OnlineLyricsCandidate> {
        if (title.isBlank()) return emptyList()
        val query = buildList {
            add("track_name=${encode(title)}")
            artist?.takeIf { it.isNotBlank() }?.let { add("artist_name=${encode(it)}") }
        }.joinToString("&")
        val connection = URL("$ENDPOINT?$query").openConnection() as HttpURLConnection
        return try {
            connection.requestMethod = "GET"
            connection.connectTimeout = 8_000
            connection.readTimeout = 12_000
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("User-Agent", "MediaAnvil/1.4 (Android; personal music player)")
            connection.setRequestProperty("Lrclib-Client", "MediaAnvil-1.4")
            check(connection.responseCode in 200..299) { "http_${connection.responseCode}" }
            val bytes = connection.inputStream.use { input ->
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(16 * 1024)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    check(output.size() + read <= MAX_RESPONSE_BYTES) { "response_too_large" }
                    output.write(buffer, 0, read)
                }
                output.toByteArray()
            }
            parse(String(bytes, StandardCharsets.UTF_8))
        } finally {
            connection.disconnect()
        }
    }

    internal fun parse(json: String): List<OnlineLyricsCandidate> {
        val array = JSONArray(json)
        return buildList {
            for (index in 0 until array.length()) {
                val item = array.optJSONObject(index) ?: continue
                val synced = item.optString("syncedLyrics").takeUnless { it.isBlank() || it == "null" } ?: continue
                if (item.optBoolean("instrumental", false)) continue
                add(
                    OnlineLyricsCandidate(
                        id = item.optLong("id", -1L),
                        trackName = item.optString("trackName"),
                        artistName = item.optString("artistName"),
                        albumName = item.optString("albumName"),
                        durationSeconds = item.optDouble("duration", 0.0).toInt(),
                        syncedLyrics = synced,
                    ),
                )
            }
        }
    }

    private fun encode(value: String): String = URLEncoder.encode(value, StandardCharsets.UTF_8.name())

    private fun candidateDoesNotMatch(track: AudioTrack, candidate: OnlineLyricsCandidate): Boolean {
        val expectedTitles = setOf(normalize(track.title), normalize(stripVersionQualifier(track.title)))
        val titleMismatch = normalize(candidate.trackName) !in expectedTitles
        val expectedArtist = normalize(track.artist.orEmpty())
        val actualArtist = normalize(candidate.artistName)
        val artistMismatch = expectedArtist.isNotEmpty() &&
            actualArtist.isNotEmpty() &&
            expectedArtist !in actualArtist && actualArtist !in expectedArtist
        val wantedDuration = (track.durationMs / 1_000L).toInt()
        val durationMismatch = wantedDuration > 0 && candidate.durationSeconds > 0 &&
            abs(candidate.durationSeconds - wantedDuration) > 8
        return titleMismatch || artistMismatch || durationMismatch
    }

    private fun normalize(value: String): String =
        value.lowercase().replace(Regex("[^\\p{L}\\p{N}]"), "")
}
