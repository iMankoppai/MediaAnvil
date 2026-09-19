package com.imankoppai.mediaanvil.ui

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.Icons
import androidx.compose.material3.Button
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.media3.session.MediaController
import com.imankoppai.mediaanvil.ui.theme.ThemeController
import com.imankoppai.mediaanvil.R
import com.imankoppai.mediaanvil.data.PlayerDataBackup
import com.imankoppai.mediaanvil.update.AppUpdateChecker
import kotlinx.coroutines.delay
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
internal fun SettingsPage(library: LibraryState, controller: MediaController?) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var message by remember { mutableStateOf<String?>(null) }
    var sleepDialog by remember { mutableStateOf(false) }
    var nowMs by remember { mutableLongStateOf(System.currentTimeMillis()) }
    var seekBackSeconds by remember { mutableIntStateOf(library.preferences.seekBackSeconds) }
    var seekForwardSeconds by remember { mutableIntStateOf(library.preferences.seekForwardSeconds) }
    // SharedPreferences is not Compose-observable; mirror settings locally so the
    // chips and switches refresh immediately instead of after re-entering the page.
    var language by remember { mutableStateOf(library.preferences.language) }
    var doublePressAction by remember { mutableStateOf(library.preferences.doublePressAction) }
    var checkingUpdate by remember { mutableStateOf(false) }
    var pendingImport by remember { mutableStateOf<Uri?>(null) }
    val currentVersion = remember {
        context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: "0"
    }
    val exportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/json"),
    ) { uri ->
        uri ?: return@rememberLauncherForActivityResult
        scope.launch {
            val result = withContext(Dispatchers.IO) {
                runCatching { PlayerDataBackup.export(context, uri, library.preferences) }
            }
            message = context.getString(
                if (result.isSuccess) R.string.backup_exported else R.string.backup_export_failed,
            )
        }
    }
    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri -> if (uri != null) pendingImport = uri }
    LaunchedEffect(library.sleepTimerEndAt) {
        nowMs = System.currentTimeMillis()
        while (library.sleepTimerEndAt != null) {
            delay(5_000)
            nowMs = System.currentTimeMillis()
        }
    }

    @androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
    fun closeApp() {
        runCatching {
            context.stopService(Intent(context, com.imankoppai.mediaanvil.playback.PlaybackService::class.java))
        }
        (context as? android.app.Activity)?.finishAffinity()
    }

    /** Sleep-timer fire: pause now, or after the current track ends; optionally close the app. */
    @androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
    fun onSleepTimerFired() {
        val finishTrack = library.preferences.sleepFinishTrack
        val closeApp = library.preferences.sleepCloseApp
        fun sendServiceAction(action: String) {
            runCatching {
                controller?.sendCustomCommand(
                    androidx.media3.session.SessionCommand(action, android.os.Bundle.EMPTY),
                    android.os.Bundle.EMPTY,
                )
            }
        }
        val stopNow = {
            controller?.pause()
            sendServiceAction(com.imankoppai.mediaanvil.playback.PlaybackService.COMMAND_STOP_AFTER_OFF)
            if (closeApp) closeApp()
        }
        if (finishTrack && controller?.isPlaying == true) {
            val player = checkNotNull(controller)
            // An active A/B loop would keep the track from ever ending, and the
            // service must not wrap the list around when this track finishes.
            sendServiceAction(com.imankoppai.mediaanvil.playback.PlaybackService.COMMAND_LOOP_CLEAR)
            sendServiceAction(com.imankoppai.mediaanvil.playback.PlaybackService.COMMAND_STOP_AFTER_ON)
            player.addListener(object : androidx.media3.common.Player.Listener {
                override fun onPlaybackStateChanged(playbackState: Int) {
                    if (playbackState == androidx.media3.common.Player.STATE_ENDED) {
                        player.removeListener(this)
                        stopNow()
                    }
                }

                override fun onMediaItemTransition(
                    mediaItem: androidx.media3.common.MediaItem?,
                    reason: Int,
                ) {
                    player.removeListener(this)
                    stopNow()
                }
            })
        } else {
            stopNow()
        }
    }

    fun applyLanguage(tag: String) {
        language = tag
        library.preferences.language = tag
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            val localeManager = context.getSystemService(android.app.LocaleManager::class.java)
            localeManager.applicationLocales =
                if (tag.isEmpty()) android.os.LocaleList.getEmptyLocaleList()
                else android.os.LocaleList.forLanguageTags(tag)
        } else {
            message = context.getString(R.string.language_needs_13)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp),
    ) {
        Text(
            stringResource(R.string.tab_settings),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(vertical = 12.dp),
        )

        // The update card sits just above About, at the bottom of the page.
        SettingsCard(title = stringResource(R.string.settings_general_section)) {
            Text(stringResource(R.string.settings_language), style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                FilterChip(
                    selected = language.isEmpty(),
                    onClick = { applyLanguage("") },
                    label = { Text(stringResource(R.string.language_system)) },
                )
                FilterChip(
                    selected = language == "zh-CN",
                    onClick = { applyLanguage("zh-CN") },
                    label = { Text("简体中文") },
                )
                FilterChip(
                    selected = language == "en",
                    onClick = { applyLanguage("en") },
                    label = { Text("English") },
                )
            }
        }

        SettingsCard(title = stringResource(R.string.settings_appearance_section)) {
            Text(stringResource(R.string.theme_mode), style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                FilterChip(
                    selected = ThemeController.mode.isEmpty(),
                    onClick = {
                        ThemeController.mode = ""
                        library.preferences.themeMode = ""
                    },
                    label = { Text(stringResource(R.string.theme_system)) },
                )
                FilterChip(
                    selected = ThemeController.mode == "light",
                    onClick = {
                        ThemeController.mode = "light"
                        library.preferences.themeMode = "light"
                    },
                    label = { Text(stringResource(R.string.theme_light)) },
                )
                FilterChip(
                    selected = ThemeController.mode == "dark",
                    onClick = {
                        ThemeController.mode = "dark"
                        library.preferences.themeMode = "dark"
                    },
                    label = { Text(stringResource(R.string.theme_dark)) },
                )
            }
        }

        SettingsCard(title = stringResource(R.string.settings_playback_section)) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.auto_load_lyrics), style = MaterialTheme.typography.bodyMedium)
                    Text(
                        stringResource(R.string.auto_load_lyrics_hint),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = library.autoLoadLyrics,
                    onCheckedChange = { library.updateAutoLoadLyrics(it) },
                )
            }
            HorizontalDivider(Modifier.padding(vertical = 10.dp))
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.show_lyrics_timestamps), style = MaterialTheme.typography.bodyMedium)
                    Text(
                        stringResource(R.string.show_lyrics_timestamps_hint),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = library.showLyricsTimestamps,
                    onCheckedChange = { library.updateShowLyricsTimestamps(it) },
                )
            }
            HorizontalDivider(Modifier.padding(vertical = 10.dp))
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.resume_playback), style = MaterialTheme.typography.bodyMedium)
                    Text(
                        stringResource(R.string.resume_playback_hint),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = library.resumePlayback,
                    onCheckedChange = { library.updateResumePlayback(it) },
                )
            }
            HorizontalDivider(Modifier.padding(vertical = 10.dp))
            SeekIntervalSetting(
                title = stringResource(R.string.seek_back_setting),
                selectedSeconds = seekBackSeconds,
                choices = listOf(5, 10, 15, 30),
                onSelected = {
                    seekBackSeconds = it
                    library.preferences.seekBackSeconds = it
                },
            )
            Spacer(Modifier.height(10.dp))
            SeekIntervalSetting(
                title = stringResource(R.string.seek_forward_setting),
                selectedSeconds = seekForwardSeconds,
                choices = listOf(10, 15, 30, 60),
                onSelected = {
                    seekForwardSeconds = it
                    library.preferences.seekForwardSeconds = it
                },
            )
        }

        var scanMode by remember { mutableStateOf(library.preferences.libraryScanMode) }
        var scanFolders by remember { mutableStateOf(library.preferences.scanFolders) }
        fun updateScanFolders(updated: Set<String>) {
            scanFolders = updated
            library.preferences.scanFolders = updated
            library.rescan(quiet = true)
        }
        val pickFolderLauncher = rememberLauncherForActivityResult(
            ActivityResultContracts.StartActivityForResult(),
        ) { result ->
            android.util.Log.d("MediaAnvilUpdate", "picker result code=${result.resultCode} data=${result.data}")
            val uri = result.data?.data ?: return@rememberLauncherForActivityResult
            val folder = com.imankoppai.mediaanvil.data.DeviceAudioLibrary.treeUriToRelativeFolder(uri)
            android.util.Log.d("MediaAnvilUpdate", "picker folder=$folder")
            if (folder != null && folder !in scanFolders) {
                updateScanFolders(scanFolders + folder)
            }
        }
        fun launchFolderPicker() {
            pickFolderLauncher.launch(
                com.imankoppai.mediaanvil.data.DeviceAudioLibrary.folderPickerIntent(context),
            )
        }
        SettingsCard(title = stringResource(R.string.scan_scope)) {
            Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = scanMode == "all",
                    onClick = {
                        if (scanMode != "all") {
                            scanMode = "all"
                            library.preferences.libraryScanMode = "all"
                            library.rescan(quiet = true)
                        }
                    },
                    label = { Text(stringResource(R.string.scan_mode_all)) },
                )
                FilterChip(
                    selected = scanMode == "folders",
                    onClick = {
                        if (scanMode != "folders") {
                            scanMode = "folders"
                            library.preferences.libraryScanMode = "folders"
                            library.rescan(quiet = true)
                        }
                    },
                    label = { Text(stringResource(R.string.scan_mode_folders)) },
                )
            }
            if (scanMode == "folders") {
                Text(
                    stringResource(R.string.scan_folders_hint),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 8.dp),
                )
                OutlinedButton(
                    onClick = { launchFolderPicker() },
                    modifier = Modifier.padding(top = 10.dp),
                ) { Text(stringResource(R.string.scan_add_folder)) }
                scanFolders.sorted().forEach { folder ->
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            folder.trimEnd('/'),
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.weight(1f),
                        )
                        androidx.compose.material3.IconButton(onClick = {
                            updateScanFolders(scanFolders - folder)
                        }) {
                            androidx.compose.material3.Icon(
                                Icons.Filled.Close,
                                contentDescription = stringResource(R.string.delete_action),
                            )
                        }
                    }
                }
            }
        }

        val sleepRemaining = library.sleepTimerEndAt?.let { end ->
            ((end - nowMs) / 60_000).toInt().coerceAtLeast(1)
        }
        SettingsCard(title = stringResource(R.string.sleep_timer)) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Text(
                    if (sleepRemaining != null) stringResource(R.string.sleep_timer_remaining, sleepRemaining)
                    else stringResource(R.string.sleep_timer_off),
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (sleepRemaining != null) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.weight(1f),
                )
                if (sleepRemaining != null) {
                    OutlinedButton(onClick = { library.cancelSleepTimer() }) {
                        Text(stringResource(R.string.sleep_timer_off))
                    }
                    Spacer(Modifier.width(8.dp))
                }
                Button(onClick = { sleepDialog = true }) {
                    Text(stringResource(R.string.sleep_timer_set))
                }
            }
        }
        if (sleepDialog) {
            SleepTimerDialog(
                initialMinutes = sleepRemaining ?: 30,
                preferences = library.preferences,
                onStart = { minutes -> library.startSleepTimer(minutes) { onSleepTimerFired() } },
                onDismiss = { sleepDialog = false },
            )
        }

        SettingsCard(title = stringResource(R.string.headset_section)) {
            Text(stringResource(R.string.headset_double), style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                listOf(
                    "" to R.string.headset_double_next,
                    "previous" to R.string.headset_double_previous,
                    "pause" to R.string.headset_double_pause,
                ).forEach { (value, labelRes) ->
                    FilterChip(
                        selected = doublePressAction == value,
                        onClick = {
                            doublePressAction = value
                            library.preferences.doublePressAction = value
                        },
                        label = { Text(stringResource(labelRes)) },
                    )
                }
            }
        }

        SettingsCard(title = stringResource(R.string.settings_system_section)) {
            val powerManager = context.getSystemService(android.os.PowerManager::class.java)
            val ignoring = powerManager?.isIgnoringBatteryOptimizations(context.packageName) == true
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.battery_keepalive), style = MaterialTheme.typography.bodyMedium)
                    Text(
                        stringResource(
                            if (ignoring) R.string.battery_ok else R.string.battery_hint,
                        ),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (!ignoring) {
                    OutlinedButton(onClick = {
                        runCatching {
                            context.startActivity(
                                android.content.Intent(android.provider.Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS),
                            )
                        }
                    }) { Text(stringResource(R.string.battery_go)) }
                }
            }
        }

        SettingsCard(title = stringResource(R.string.settings_data_section)) {
            Text(
                stringResource(R.string.backup_hint),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(
                horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp),
                modifier = Modifier.padding(top = 10.dp),
            ) {
                OutlinedButton(onClick = {
                    exportLauncher.launch("MediaAnvil-backup.json")
                }) { Text(stringResource(R.string.backup_export)) }
                OutlinedButton(onClick = {
                    importLauncher.launch(arrayOf("application/json", "text/plain"))
                }) { Text(stringResource(R.string.backup_import)) }
            }
        }

        library.updateRelease?.let { release ->
            SettingsCard(title = stringResource(R.string.update_banner_title, release.tagName)) {
                if (library.updateApkReady) {
                    Text(stringResource(R.string.update_ready_to_install), style = MaterialTheme.typography.bodyMedium)
                    Button(
                        onClick = { library.installDownloadedUpdate() },
                        modifier = Modifier.padding(top = 10.dp),
                    ) { Text(stringResource(R.string.update_install_button)) }
                } else if (library.updateProgress >= 0) {
                    Text(
                        stringResource(R.string.update_downloading, library.updateProgress),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    androidx.compose.material3.LinearProgressIndicator(
                        progress = { library.updateProgress.coerceIn(0, 100) / 100f },
                        modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                    )
                } else if (library.updateFailed) {
                    Text(
                        stringResource(R.string.update_download_failed),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                    )
                    Button(
                        onClick = { library.startUpdateDownload() },
                        modifier = Modifier.padding(top = 10.dp),
                    ) { Text(stringResource(R.string.update_retry)) }
                    OutlinedButton(
                        onClick = { library.dismissUpdate() },
                        modifier = Modifier.padding(top = 4.dp),
                    ) { Text(stringResource(R.string.update_dismiss)) }
                } else {
                    Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = { library.startUpdateDownload() },
                            enabled = release.apkUrl.isNotBlank(),
                        ) { Text(stringResource(R.string.update_action)) }
                        OutlinedButton(onClick = { library.dismissUpdate() }) {
                            Text(stringResource(R.string.update_dismiss))
                        }
                    }
                }
            }
        }

        SettingsCard(title = stringResource(R.string.settings_about_section)) {
            Text("MediaAnvil Mobile $currentVersion", style = MaterialTheme.typography.bodyMedium)
            Text(
                stringResource(R.string.local_only),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp),
            )
            OutlinedButton(
                enabled = !checkingUpdate,
                onClick = {
                    checkingUpdate = true
                    message = null
                    scope.launch {
                        val result = withContext(Dispatchers.IO) {
                            runCatching { AppUpdateChecker.fetchLatest() }
                        }
                        checkingUpdate = false
                        result.onSuccess { release ->
                            if (AppUpdateChecker.isNewer(release.tagName, currentVersion)) {
                                library.reportUpdateRelease(release)
                            } else {
                                message = context.getString(R.string.update_latest)
                            }
                        }.onFailure {
                            message = context.getString(R.string.update_failed)
                        }
                    }
                },
                modifier = Modifier.padding(top = 10.dp),
            ) {
                Text(stringResource(if (checkingUpdate) R.string.update_checking else R.string.update_check))
            }
        }
        message?.let {
            Text(
                it,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(vertical = 8.dp),
            )
        }
        Spacer(Modifier.height(24.dp))
    }


    pendingImport?.let { uri ->
        AlertDialog(
            onDismissRequest = { pendingImport = null },
            title = { Text(stringResource(R.string.backup_import_confirm_title)) },
            text = { Text(stringResource(R.string.backup_import_confirm_body)) },
            confirmButton = {
                Button(onClick = {
                    pendingImport = null
                    scope.launch {
                        val result = withContext(Dispatchers.IO) {
                            runCatching { PlayerDataBackup.import(context, uri, library.preferences) }
                        }
                        if (result.isSuccess) {
                            seekBackSeconds = library.preferences.seekBackSeconds
                            seekForwardSeconds = library.preferences.seekForwardSeconds
                            ThemeController.mode = library.preferences.themeMode
                            library.reloadAfterPreferencesRestore()
                            message = context.getString(R.string.backup_imported)
                        } else {
                            message = context.getString(R.string.backup_import_failed)
                        }
                    }
                }) { Text(stringResource(R.string.confirm)) }
            },
            dismissButton = {
                OutlinedButton(onClick = { pendingImport = null }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }
}

@Composable
private fun SeekIntervalSetting(
    title: String,
    selectedSeconds: Int,
    choices: List<Int>,
    onSelected: (Int) -> Unit,
) {
    Text(title, style = MaterialTheme.typography.bodyMedium)
    androidx.compose.foundation.lazy.LazyRow(
        horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp),
        modifier = Modifier.padding(top = 6.dp),
    ) {
        items(choices.size) { index ->
            val seconds = choices[index]
            FilterChip(
                selected = selectedSeconds == seconds,
                onClick = { onSelected(seconds) },
                label = { Text(stringResource(R.string.seconds_value, seconds)) },
            )
        }
    }
}

@Composable
private fun SettingsCard(title: String, content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surface,
        modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(
                title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(bottom = 8.dp),
            )
            content()
        }
    }
}
