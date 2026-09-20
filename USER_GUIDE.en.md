# MediaAnvil User Guide

**[简体中文 →](USER_GUIDE.md)**

Applies to: MediaAnvil Qt 1.0.1 for Windows

MediaAnvil is a local media toolbox for audio playback with synchronized lyrics, audio metadata and artwork editing, lyrics and subtitle conversion, audio and image conversion, and metadata-based batch renaming. All media processing happens on your computer.

## 1. Installation and startup

1. Extract or copy the complete `MediaAnvilQt` folder.
2. Double-click `MediaAnvilQt.exe` inside that folder.
3. MediaAnvil opens on the Audio Preview page.

The application targets a centered `1440 × 900` (16:10) window on every launch. It scales down proportionally on smaller or high-DPI displays so the window remains on screen.

Keep the complete `MediaAnvilQt` folder. Do not copy the EXE by itself because required components are stored in the adjacent `_internal` directory.

Windows SmartScreen may display a warning on first launch. Confirm that the file came from the trusted project release before choosing More info and continuing.

## 2. Interface and common operations

The navigation bar contains:

- Audio Preview
- Tag Editor
- Lyrics / Subtitles
- Audio Converter
- Image Converter
- Batch Rename
- Settings
- About

Most pages accept files or folders dragged directly from Windows File Explorer. Whether folders include nested directories is controlled by Settings → File Scanning → Include Subfolders. Batch Rename also provides its own Include Subfolders option.

Files on conversion pages are selected by default. Clear a file's checkbox to exclude it from the current operation. Remove only removes files from the on-screen list; it never deletes source files from disk.

## 3. Audio Preview

### Open and play audio

1. Open Audio Preview.
2. Select Choose Audio and choose an audio file.
3. Use the central button to play or pause.
4. Use the buttons on either side to go back or forward by 30 seconds.

Click or drag the progress bar to seek. Use the lower slider to adjust volume. Press Space to play or pause.

### Synchronized lyrics

MediaAnvil can automatically load a matching `.lrc`, `.srt`, or `.vtt` file beside the audio, for example:

```text
song.mp3
song.lrc (or song.srt / song.vtt)
```

Names that retain the audio extension are also supported, such as `song.wav.vtt`, `song.flac.srt`, and `song.mp3.lrc`. If both naming styles exist for the same subtitle format, the file containing the complete audio filename takes priority.

When Auto-load Matching Lyrics is enabled, MediaAnvil reads the matching file directly without converting or modifying it. The default priority is LRC, SRT, VTT, then embedded synchronized MP3 lyrics.

When Prefer Embedded MP3 Lyrics is enabled, usable synchronized lyrics embedded in an MP3 take priority. If none are available, MediaAnvil falls back to LRC, SRT, and VTT in that order. This option does not affect other audio formats.

During playback, the current line is highlighted and centered automatically. Click a line to seek to its timestamp. Multiline SRT/VTT cues retain their line breaks, and highlighting ends when a cue reaches its end time. Audio playback remains available when no synchronized lyrics are found.

Preview supports MP3, WAV, FLAC, M4A, AAC, OGG, and Opus.

## 4. Tag Editor

### Edit basic information

1. Open Tag Editor.
2. Select Choose Audio.
3. Edit the title, artist, and album.
4. Choose the save mode and output folder.
5. Select Save to Audio.

Save As is the default and leaves the source file unchanged. The source is replaced only when Overwrite Source is explicitly selected.

Writable formats are MP3, FLAC, M4A, OGG, and Opus. WAV metadata can be read but not saved. AAC is not supported by the tag editor.

### Lyrics

- Import Lyrics / Subtitles accepts LRC, SRT, and VTT. SRT/VTT content is converted to LRC internally before embedding; the original subtitle is not modified and no extra file is created.
- Export Lyrics exports lyrics embedded in the current audio file.
- Remove lyrics when saving removes embedded lyrics during the next save.

Timed lyrics are embedded as LRC for compatibility. Exported synchronized lyrics are also written as LRC.

### Artwork

- Choose Image opens the rectangular crop window immediately. Drag to create or move the crop area, or enter its left, top, width, and height in pixels. The complete image is selected initially. Confirm to import the cropped result or cancel to keep the current artwork.
- Export Image exports the embedded artwork.
- Remove artwork when saving removes embedded artwork during the next save.

JPG, JPEG, PNG, WebP, and BMP images can be selected. The artwork preview expands with the available space. Crops may be square, landscape, or portrait. MediaAnvil converts the result to image data supported by the target audio metadata format before writing it.

### Smart File Matching

Smart File Matching is collapsed by default. Expand it to scan a music folder and find lyrics and artwork candidates by filename.

The matcher understands associated files that retain the audio extension, including `song.wav.vtt`, `song.wav.png`, and `song.flac.lrc`. Within the same format, these complete-name candidates take priority over names such as `song.vtt` and `song.png`.

Clear Files only clears the scan results and candidate lists; it never deletes audio, lyrics, subtitle, or image files from disk.

Matching priority is exact name, name with spaces ignored, then names with copy markers or parenthesized numbers removed. If several candidates have equal priority, MediaAnvil does not select one automatically—you must choose explicitly.

## 5. Lyrics / Subtitle Converter

LRC, SRT, and VTT can be converted in any direction.

1. Select Add Files or drop files into the dashed area.
2. Confirm that the files to process are checked.
3. Choose the output format.
4. If needed, configure the duration of the final LRC line.
5. Choose an output folder, or leave it blank to save beside each source file.
6. Select Start Batch Conversion.
7. Choose a result on the right to inspect the converted text.

LRC normally has no end timestamps. When converting to SRT or VTT, each ordinary line ends when the next line starts. The final line uses the configured duration, which defaults to five seconds.

Converted text is written as UTF-8 with BOM. If the target filename already exists, MediaAnvil creates a safe name with `_1`, `_2`, and so on instead of overwriting it.

## 6. Audio Converter

Supported input and output formats are MP3, WAV, FLAC, M4A, AAC, and OGG.

1. Select Add Files or drop audio into the dashed area.
2. Choose the output format.
3. Select the bitrate, compression level, or quality appropriate for that format.
4. Choose a sample rate and channel layout as needed. Keep Original is suitable for most files.
5. Choose whether to preserve audio metadata.
6. Choose an output folder and select Start Batch Conversion.

Common options:

| Option | Values |
| --- | --- |
| MP3 bitrate | 128, 192, 256, 320 kbps |
| AAC / M4A bitrate | 96, 128, 192, 256 kbps |
| FLAC compression | 0, 5, 8 |
| OGG quality | 3, 5, 7, 9 |
| Sample rate | Keep Original, 44100, 48000, 96000 Hz |
| Channels | Keep Original, Mono, Stereo |

MediaAnvil rejects a no-op conversion when the source and output formats are identical. The bundled FFmpeg performs audio conversion; no separate installation is required.

## 7. Image Converter

JPG/JPEG, PNG, WebP, and BMP can be converted in any direction.

1. Select Add Images or drop images into the dashed area.
2. Choose the output format.
3. Set quality from 1 to 100 for JPG or WebP output.
4. Choose an output folder and select Start Batch Conversion.
5. Review converted files and image previews on the right.

MediaAnvil preserves source dimensions. PNG and WebP can retain transparency; transparent pixels are placed on a white background when converting to JPG or BMP.

## 8. Batch Rename

Batch Rename generates filenames from audio metadata. It does not re-encode audio or change metadata.

Supported formats are MP3, FLAC, M4A, OGG, and Opus.

1. Select Add Files or drop audio files or a folder onto the page.
2. Choose a rename template.
3. Use the variable buttons to insert metadata fields.
4. Select Refresh Preview.
5. Review the original filename, new filename, and status.
6. Check the items to process, then select Start Renaming.

Available variables:

| Variable | Meaning |
| --- | --- |
| `{artist}` | Artist |
| `{title}` | Title |
| `{album}` | Album |
| `{track}` | Track number |
| `{year}` | Year |

Use original filename for missing fields prevents incomplete metadata from immediately blocking an item. Invalid filename characters are handled safely and conflicts are shown in the preview.

Export Preview saves the current plan as CSV. Undo Last Rename applies only to the most recent successful batch. MediaAnvil will not overwrite another file if it has taken an original filename.

## 9. Settings

Settings apply to subsequent tasks:

- General: default output location, save mode, and interface language.
- Audio Conversion: default MP3/AAC bitrate, sample-rate and channel preservation, and metadata preservation.
- Image Conversion: default JPG/WebP quality and original-dimension preservation.
- Lyrics & Preview: final LRC duration, default volume, automatic matching-lyrics loading, and embedded MP3 lyrics priority.
- File Scanning: whether to include subfolders.

Select Save Settings after making changes. Restore Defaults resets the controls on the page; select Save Settings to write those restored values to the configuration file.

### Switch languages

Open Settings → General → Language, choose Chinese or English, and select Save Settings. The interface changes immediately and keeps the selected language on the next launch.

The settings file is stored at:

```text
%APPDATA%\MediaAnvilQt\settings.json
```

MediaAnvil restores safe defaults if the settings file is damaged.

## 10. Output and file safety

- Conversion never overwrites source files.
- Existing target names receive a safe new filename automatically.
- The tag editor defaults to Save As.
- Metadata overwrite operations work through and validate a temporary copy first.
- Remove and Clear affect only task lists inside MediaAnvil; they never delete disk files.
- Batch Rename changes filenames only, not audio content.

The content area may be temporarily disabled during processing. Wait for the task to finish before closing the application to avoid interrupting a write.

## 11. Troubleshooting

### Nothing happens when I double-click the EXE

Confirm that `_internal` and `MediaAnvilQt.exe` are in the same release folder. Do not copy the EXE by itself.

### A dropped file does not appear

Confirm that the current page supports its extension. When dropping a folder, check whether Include Subfolders matches your intended scan scope.

### Audio plays but synchronized lyrics are missing

Confirm that the lyrics or subtitle file is beside the audio and uses a matching base name. Also check that Auto-load Matching Lyrics is enabled.

### I cannot find a converted file

When Output Folder is blank, each result is saved beside its source file. You can also select Open File Location from the results panel.

### WAV metadata cannot be saved

WAV is currently read-only in the tag editor. Convert the file to MP3, FLAC, M4A, OGG, or Opus if you need writable metadata.

### The target format matches the source format

Audio Converter does not perform same-format re-encoding. Choose a different output format.

### A converted JPG has no transparency

JPG does not support transparency. MediaAnvil fills transparent pixels with white; use PNG or WebP when transparency is required.

## 12. Third-party components

MediaAnvil includes Qt/PySide6, ICU, FFmpeg, and FFplay. License information is provided in `THIRD_PARTY_NOTICES.md` and the `licenses` directory inside the release folder.
