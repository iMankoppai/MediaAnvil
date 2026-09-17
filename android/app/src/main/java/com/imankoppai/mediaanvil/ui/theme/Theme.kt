package com.imankoppai.mediaanvil.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color

// Desktop visual language: light blue canvas, white rounded cards, #1677FF accent.
private val LightColors = lightColorScheme(
    primary = Color(0xFF1677FF),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD8E8FF),
    onPrimaryContainer = Color(0xFF082B62),
    secondary = Color(0xFF43536D),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFE3EAF5),
    onSecondaryContainer = Color(0xFF1B2A44),
    tertiary = Color(0xFF22B07D),
    background = Color(0xFFF4F8FF),
    onBackground = Color(0xFF16233B),
    surface = Color.White,
    onSurface = Color(0xFF16233B),
    surfaceVariant = Color(0xFFE9F0FA),
    onSurfaceVariant = Color(0xFF5A6B85),
    outlineVariant = Color(0xFFDCE6F4),
    error = Color(0xFFD4383E),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF6FB1FF),
    onPrimary = Color(0xFF00315F),
    primaryContainer = Color(0xFF134A85),
    onPrimaryContainer = Color(0xFFD5E6FF),
    secondary = Color(0xFFAFC4E3),
    onSecondary = Color(0xFF1B2A44),
    secondaryContainer = Color(0xFF2D3F5A),
    onSecondaryContainer = Color(0xFFDCE6F8),
    tertiary = Color(0xFF5BD3A2),
    background = Color(0xFF0F1725),
    onBackground = Color(0xFFDCE5F2),
    surface = Color(0xFF162135),
    onSurface = Color(0xFFDCE5F2),
    surfaceVariant = Color(0xFF22304A),
    onSurfaceVariant = Color(0xFF96A7C2),
    outlineVariant = Color(0xFF2C3B55),
    error = Color(0xFFFF8B90),
)

/** Observable mirror of the persisted theme prefs so toggles apply without recreation. */
object ThemeController {
    var mode by mutableStateOf("")

    fun load(preferences: com.imankoppai.mediaanvil.data.PlaybackPreferences) {
        mode = preferences.themeMode
    }
}

@Composable
fun MediaAnvilTheme(
    darkTheme: Boolean,
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
