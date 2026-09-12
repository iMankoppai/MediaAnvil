package com.imankoppai.mediaanvil.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.MergeType
import androidx.compose.material.icons.filled.ContentCut
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Sell
import androidx.compose.material.icons.filled.SyncAlt
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.media3.session.MediaController
import com.imankoppai.mediaanvil.ui.theme.ThemeController
import com.imankoppai.mediaanvil.R
import com.imankoppai.mediaanvil.model.AudioTrack
import com.imankoppai.mediaanvil.playback.EqController
import com.imankoppai.mediaanvil.tools.AudioConverter
import com.imankoppai.mediaanvil.tools.ImageTarget
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Tools hub mirroring the desktop sidebar's tool pages. */
@Composable
internal fun ToolsHubPage(
    library: LibraryState,
    onOpenEditor: (AudioTrack?) -> Unit,
    onOpenTool: (ToolKind) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var message by remember { mutableStateOf<String?>(null) }

    data class HubEntry(
        val icon: ImageVector,
        val title: String,
        val subtitle: String,
        val onClick: () -> Unit,
    )

    val entries = listOf(
        HubEntry(
            Icons.Filled.Sell,
            stringResource(R.string.tab_tag_editor),
            stringResource(R.string.tool_edit_tags_sub),
        ) { onOpenEditor(library.selectedTrack) },
        HubEntry(
            Icons.Filled.Description,
            stringResource(R.string.tool_lyrics_convert),
            stringResource(R.string.tool_lyrics_convert_sub),
        ) { onOpenTool(ToolKind.LyricsConvert) },
        HubEntry(
            Icons.Filled.SyncAlt,
            stringResource(R.string.tool_audio_convert),
            stringResource(R.string.tool_audio_convert_sub),
        ) { onOpenTool(ToolKind.AudioConvert) },
        HubEntry(
            Icons.Filled.Image,
            stringResource(R.string.tool_image_convert),
            stringResource(R.string.tool_image_convert_sub),
        ) { onOpenTool(ToolKind.ImageConvert) },
        HubEntry(
            Icons.Filled.ContentCut,
            stringResource(R.string.tool_audio_clip),
            stringResource(R.string.tool_audio_clip_sub),
        ) { onOpenTool(ToolKind.AudioClip) },
        HubEntry(
            Icons.AutoMirrored.Filled.MergeType,
            stringResource(R.string.tool_audio_merge),
            stringResource(R.string.tool_audio_merge_sub),
        ) { onOpenTool(ToolKind.AudioMerge) },
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp),
    ) {
        Text(
            stringResource(R.string.tab_tools),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(vertical = 12.dp),
        )
        entries.forEach { entry ->
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surface,
                modifier = Modifier.fillMaxWidth().padding(vertical = 5.dp),
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable(enabled = true, onClick = entry.onClick)
                        .padding(horizontal = 14.dp, vertical = 14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        entry.icon,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(26.dp),
                    )
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Text(entry.title, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold)
                        Text(
                            entry.subtitle,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Icon(
                        Icons.Filled.KeyboardArrowRight,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
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
    }
}

@Composable
internal fun SettingsPage(library: LibraryState, controller: MediaController?) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var message by remember { mutableStateOf<String?>(null) }
    var sleepDialog by remember { mutableStateOf(false) }
    var nowMs by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(library.sleepTimerEndAt) {
        nowMs = System.currentTimeMillis()
        while (library.sleepTimerEndAt != null) {
            delay(5_000)
            nowMs = System.currentTimeMillis()
        }
    }

    fun applyLanguage(tag: String) {
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

        SettingsCard(title = stringResource(R.string.settings_general_section)) {
            Text(stringResource(R.string.settings_language), style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                FilterChip(
                    selected = library.preferences.language.isEmpty(),
                    onClick = { applyLanguage("") },
                    label = { Text(stringResource(R.string.language_system)) },
                )
                FilterChip(
                    selected = library.preferences.language == "zh-CN",
                    onClick = { applyLanguage("zh-CN") },
                    label = { Text("简体中文") },
                )
                FilterChip(
                    selected = library.preferences.language == "en",
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
            HorizontalDivider(Modifier.padding(vertical = 8.dp))
            if (android.os.Build.VERSION.SDK_INT >= 31) {
                SettingToggle(
                    title = stringResource(R.string.theme_dynamic_color),
                    hint = stringResource(R.string.theme_dynamic_color_hint),
                    checked = ThemeController.useDynamicColor,
                    onChange = {
                        ThemeController.useDynamicColor = it
                        library.preferences.useDynamicColor = it
                    },
                )
                HorizontalDivider(Modifier.padding(vertical = 8.dp))
            }
            SettingToggle(
                title = stringResource(R.string.theme_cover_color),
                hint = stringResource(R.string.theme_cover_color_hint),
                checked = ThemeController.useCoverColor,
                onChange = {
                    ThemeController.useCoverColor = it
                    library.preferences.useCoverColor = it
                    if (it) refreshCoverSeed(context, library, scope, controller?.currentMediaItem?.mediaId)
                },
            )
        }

        SettingsCard(title = stringResource(R.string.settings_playback_section)) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.prefer_embedded), style = MaterialTheme.typography.bodyMedium)
                    Text(
                        stringResource(R.string.prefer_embedded_hint),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = library.preferences.preferEmbeddedLyrics,
                    onCheckedChange = { library.preferences.preferEmbeddedLyrics = it },
                )
            }
            HorizontalDivider(Modifier.padding(vertical = 8.dp))
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
                    checked = library.preferences.autoLoadLyrics,
                    onCheckedChange = { library.preferences.autoLoadLyrics = it },
                )
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
                onStart = { minutes -> library.startSleepTimer(minutes) { controller?.pause() } },
                onDismiss = { sleepDialog = false },
            )
        }

        SettingsCard(title = stringResource(R.string.settings_sound_section)) {
            var gain by remember { mutableIntStateOf(library.preferences.loudnessGainDb) }
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.loudness_gain), style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.weight(1f))
                Text(
                    if (gain > 0) stringResource(R.string.loudness_gain_value, gain)
                    else stringResource(R.string.loudness_gain_off),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            androidx.compose.material3.Slider(
                value = gain.toFloat(),
                onValueChange = {
                    gain = it.toInt()
                    library.preferences.loudnessGainDb = gain
                    com.imankoppai.mediaanvil.playback.LoudnessGain.setGain(gain)
                },
                valueRange = 0f..12f,
                steps = 11,
                modifier = Modifier.fillMaxWidth(),
            )
            Text(
                stringResource(R.string.loudness_gain_hint),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        SettingsCard(title = stringResource(R.string.headset_section)) {
            Text(stringResource(R.string.headset_double), style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                listOf(
                    "" to R.string.headset_double_next,
                    "previous" to R.string.headset_double_previous,
                    "speed" to R.string.headset_double_speed,
                    "none" to R.string.headset_double_none,
                ).forEach { (value, labelRes) ->
                    FilterChip(
                        selected = library.preferences.doublePressAction == value,
                        onClick = { library.preferences.doublePressAction = value },
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

        SettingsCard(title = stringResource(R.string.settings_eq_section)) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Text(
                    stringResource(R.string.settings_eq_enable),
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.weight(1f),
                )
                Switch(
                    checked = EqController.enabled,
                    onCheckedChange = { EqController.applyEnabled(it) },
                )
            }
            if (EqController.presets.isEmpty()) {
                Text(
                    stringResource(R.string.eq_hint),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp),
                )
            } else {
                androidx.compose.foundation.lazy.LazyRow(
                    horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 4.dp),
                    modifier = Modifier.padding(top = 8.dp),
                ) {
                    items(EqController.presets.size) { index ->
                        FilterChip(
                            selected = EqController.selectedPreset == index,
                            onClick = { EqController.setPreset(index) },
                            enabled = EqController.enabled,
                            label = { Text(EqController.presets[index]) },
                        )
                    }
                }
            }
        }

        SettingsCard(title = stringResource(R.string.settings_lyrics_section)) {
            Text(stringResource(R.string.settings_lrc_tail), style = MaterialTheme.typography.bodyMedium)
            androidx.compose.foundation.lazy.LazyRow(
                horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 4.dp),
                modifier = Modifier.padding(top = 8.dp),
            ) {
                items(5) { index ->
                    val seconds = listOf(2, 3, 5, 8, 10)[index]
                    FilterChip(
                        selected = library.preferences.lrcTailSeconds == seconds,
                        onClick = { library.preferences.lrcTailSeconds = seconds },
                        label = { Text(stringResource(R.string.lrc_tail_seconds, seconds)) },
                    )
                }
            }
        }

        SettingsCard(title = stringResource(R.string.settings_scan_section)) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.include_subfolders), style = MaterialTheme.typography.bodyMedium)
                    Text(
                        stringResource(R.string.include_subfolders_hint),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = library.preferences.includeSubfolders,
                    onCheckedChange = { checked ->
                        library.preferences.includeSubfolders = checked
                        library.rescan(quiet = true)
                    },
                )
            }
        }

        SettingsCard(title = stringResource(R.string.settings_convert_section)) {
            Text(stringResource(R.string.settings_default_audio_format), style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                AudioConverter.targets.forEach { target ->
                    val ext = target.extension
                    FilterChip(
                        selected = library.preferences.audioConvertTarget == ext,
                        onClick = { library.preferences.audioConvertTarget = ext },
                        label = { Text(ext.uppercase()) },
                    )
                }
            }
            Text(
                stringResource(R.string.settings_default_image_format),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 12.dp),
            )
            Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                ImageTarget.entries.forEach { target ->
                    FilterChip(
                        selected = library.preferences.imageConvertTarget == target.extension,
                        onClick = { library.preferences.imageConvertTarget = target.extension },
                        label = { Text(target.extension.uppercase()) },
                    )
                }
            }
        }

        SettingsCard(title = stringResource(R.string.settings_save_section)) {
            Text(
                stringResource(R.string.settings_default_save_mode),
                style = MaterialTheme.typography.bodyMedium,
            )
            Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                FilterChip(
                    selected = !library.preferences.defaultOverwrite,
                    onClick = { library.preferences.defaultOverwrite = false },
                    label = { Text(stringResource(R.string.save_as)) },
                )
                FilterChip(
                    selected = library.preferences.defaultOverwrite,
                    onClick = { library.preferences.defaultOverwrite = true },
                    label = { Text(stringResource(R.string.overwrite_original)) },
                )
            }
        }

        SettingsCard(title = stringResource(R.string.settings_about_section)) {
            Text("MediaAnvil Mobile 1.3", style = MaterialTheme.typography.bodyMedium)
            Text(
                stringResource(R.string.local_only),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp),
            )
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

@Composable
private fun SettingToggle(title: String, hint: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyMedium)
            Text(
                hint,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Switch(checked = checked, onCheckedChange = onChange)
    }
}
