package com.imankoppai.mediaanvil.update

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class AppRelease(
    val tagName: String,
    val title: String,
    val notes: String,
    val pageUrl: String,
)

object AppUpdateChecker {
    private const val LATEST_RELEASE_URL =
        "https://api.github.com/repos/iMankoppai/MediaAnvil/releases/latest"

    fun fetchLatest(): AppRelease {
        val connection = URL(LATEST_RELEASE_URL).openConnection() as HttpURLConnection
        return try {
            connection.connectTimeout = 10_000
            connection.readTimeout = 15_000
            connection.setRequestProperty("Accept", "application/vnd.github+json")
            connection.setRequestProperty("User-Agent", "MediaAnvil-Android")
            connection.setRequestProperty("X-GitHub-Api-Version", "2022-11-28")
            check(connection.responseCode in 200..299) { "http_${connection.responseCode}" }
            val json = connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            parseRelease(json)
        } finally {
            connection.disconnect()
        }
    }

    internal fun parseRelease(json: String): AppRelease {
        val item = JSONObject(json)
        val tag = item.getString("tag_name")
        return AppRelease(
            tagName = tag,
            title = item.optString("name").ifBlank { tag },
            notes = item.optString("body"),
            pageUrl = item.getString("html_url"),
        )
    }

    fun isNewer(latestTag: String, currentVersion: String): Boolean {
        val latest = versionParts(latestTag)
        val current = versionParts(currentVersion)
        val size = maxOf(latest.size, current.size)
        for (index in 0 until size) {
            val left = latest.getOrElse(index) { 0 }
            val right = current.getOrElse(index) { 0 }
            if (left != right) return left > right
        }
        return false
    }

    private fun versionParts(value: String): List<Int> =
        value.trim().removePrefix("v").removePrefix("V")
            .substringBefore('-')
            .split('.')
            .map { part -> part.takeWhile(Char::isDigit).toIntOrNull() ?: 0 }
}
