package com.imankoppai.mediaanvil.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import android.os.Build

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

/** Cover-art seed shared between the player and the theme; null = use the fixed palette. */
object ThemeSeed {
    var coverColor by mutableStateOf<Color?>(null)
}

/** Observable mirror of the persisted theme prefs so toggles apply without recreation. */
object ThemeController {
    var mode by mutableStateOf("")
    var useDynamicColor by mutableStateOf(false)
    var useCoverColor by mutableStateOf(false)

    fun load(preferences: com.imankoppai.mediaanvil.data.PlaybackPreferences) {
        mode = preferences.themeMode
        useDynamicColor = preferences.useDynamicColor
        useCoverColor = preferences.useCoverColor
    }
}

private fun mix(base: Color, target: Color, fraction: Float): Color = Color(
    red = base.red + (target.red - base.red) * fraction,
    green = base.green + (target.green - base.green) * fraction,
    blue = base.blue + (target.blue - base.blue) * fraction,
    alpha = 1f,
)

private fun onColorFor(color: Color): Color =
    if (0.299 * color.red + 0.587 * color.green + 0.114 * color.blue > 0.6) Color.Black else Color.White

/** Re-accent the base scheme with the cover color; backgrounds stay close to the base look. */
private fun seededScheme(base: ColorScheme, seed: Color): ColorScheme = base.copy(
    primary = seed,
    onPrimary = onColorFor(seed),
    primaryContainer = mix(base.background, seed, 0.28f),
    onPrimaryContainer = mix(base.onBackground, seed, 0.55f),
)

@Composable
fun MediaAnvilTheme(
    darkTheme: Boolean,
    useDynamicColor: Boolean,
    seedColor: Color?,
    content: @Composable () -> Unit,
) {
    val context = LocalContext.current
    val scheme = when {
        useDynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        seedColor != null -> seededScheme(if (darkTheme) DarkColors else LightColors, seedColor)
        darkTheme -> DarkColors
        else -> LightColors
    }
    MaterialTheme(
        colorScheme = scheme,
        content = content,
    )
}

@Composable
private fun dynamicLightColorScheme(context: android.content.Context): ColorScheme =
    androidx.compose.material3.dynamicLightColorScheme(context)

@Composable
private fun dynamicDarkColorScheme(context: android.content.Context): ColorScheme =
    androidx.compose.material3.dynamicDarkColorScheme(context)
