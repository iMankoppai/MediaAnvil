package com.imankoppai.mediaanvil.model

/** A local playlist-like group. Audio files remain in their original folders. */
data class TrackGroup(
    val id: String,
    val name: String,
    val trackUris: Set<String>,
)
