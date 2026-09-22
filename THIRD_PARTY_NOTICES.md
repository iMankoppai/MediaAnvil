# Third-party notices

## FFmpeg

The standalone Windows build of MediaAnvil includes `ffmpeg.exe` and `ffplay.exe` from the FFmpeg 9.0.2 essentials build published by gyan.dev, one of the Windows build providers linked from the official FFmpeg download page.

- FFmpeg project: https://ffmpeg.org/
- Windows build: https://www.gyan.dev/ffmpeg/builds/
- Corresponding FFmpeg source revision: https://github.com/FFmpeg/FFmpeg/commit/946fcce07b
- License information: https://ffmpeg.org/legal.html

The bundled gyan.dev essentials build is distributed under GPLv3. FFmpeg and FFplay are separate executables invoked by MediaAnvil and are not linked into the MediaAnvil Python application.

## jAudioTagger

The Android client bundles the `com.github.Kaned1as:jaudiotagger:2.3.15` library
for the optional two-field audio tag editor. It supports reading and writing the
title and artist fields for MP3, FLAC, M4A, OGG Vorbis, and Opus files. WAV
title and artist fields use MediaAnvil's built-in RIFF/INFO implementation.

- Fork source: https://github.com/Kaned1as/jaudiotagger
- Upstream project: https://www.jthink.net/jaudiotagger/
- License: GNU Lesser General Public License v2.1 or later
- License text: https://github.com/Kaned1as/jaudiotagger/blob/master/license.txt
- Original artifact: https://jitpack.io/#Kaned1as/jaudiotagger/2.3.15
