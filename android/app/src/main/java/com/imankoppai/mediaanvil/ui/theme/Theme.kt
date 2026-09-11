package com.imankoppai.mediaanvil.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
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

/** The mobile UI follows the desktop light theme; dark mode is intentionally deferred. */
@Composable
fun MediaAnvilTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightColors,
        content = content,
    )
}
