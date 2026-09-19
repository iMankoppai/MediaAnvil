package com.imankoppai.mediaanvil.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.core.content.FileProvider
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** Downloads a release APK and hands it to the system package installer. */
object AppUpdateInstaller {
    const val MAX_DOWNLOAD_BYTES = 300L * 1024 * 1024

    fun apkFile(context: Context): File = File(File(context.filesDir, "update"), "mediaanvil-update.apk")

    /** Streams [url] to the staged APK file, reporting integer percent progress. */
    fun downloadApk(context: Context, url: String, onProgress: (Int) -> Unit): File {
        val target = apkFile(context)
        target.parentFile?.mkdirs()
        val connection = URL(url).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 10_000
            connection.readTimeout = 60_000
            connection.instanceFollowRedirects = true
            connection.setRequestProperty("User-Agent", "MediaAnvil-Android")
            check(connection.responseCode in 200..299) { "http_${connection.responseCode}" }
            val total = connection.contentLengthLong.takeIf { it > 0 } ?: -1L
            connection.inputStream.use { input ->
                target.outputStream().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    var written = 0L
                    var lastPercent = -1
                    while (true) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        written += read
                        check(written <= MAX_DOWNLOAD_BYTES) { "response_too_large" }
                        output.write(buffer, 0, read)
                        if (total > 0) {
                            val percent = ((written * 100) / total).toInt().coerceIn(0, 100)
                            if (percent != lastPercent) {
                                lastPercent = percent
                                onProgress(percent)
                            }
                        }
                    }
                }
            }
            check(target.length() > 0L) { "empty_download" }
            return target
        } catch (failure: Throwable) {
            target.delete()
            throw failure
        } finally {
            connection.disconnect()
        }
    }

    /** Android 8+: the user must allow this app to install packages once. */
    fun canInstall(context: Context): Boolean = context.packageManager.canRequestPackageInstalls()

    fun unknownSourcesSettings(context: Context) {
        context.startActivity(
            Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES)
                .setData(Uri.parse("package:${context.packageName}"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        )
    }

    fun install(context: Context, apk: File) {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", apk)
        context.startActivity(
            Intent(Intent.ACTION_INSTALL_PACKAGE)
                .setData(uri)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK),
        )
    }
}
