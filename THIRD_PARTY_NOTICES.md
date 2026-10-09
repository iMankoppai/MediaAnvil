# Third-party notices

## Qt native playback

The upgraded desktop player uses Qt Multimedia supplied by the official
`PySide6-Addons==6.11.2` wheel, alongside `PySide6-Essentials==6.11.2` and Shiboken.
These components are shipped as separate dynamic libraries. Qt/PySide source
and license information is described in `README-Qt.md` and `licenses/qt/`.

Qt Multimedia's FFmpeg backend uses the FFmpeg libraries shipped with that Qt
distribution. They are separate from the gyan.dev command-line binaries below.
The Qt backend's upstream attribution, license texts and source/build references
are available in the matching Qt documentation:

- https://doc.qt.io/qt-6.11/qtmultimedia-attribution-ffmpeg.html
- https://code.qt.io/cgit/qt/qtmultimedia.git/tree/src/3rdparty/ffmpeg?h=6.11.2
- https://code.qt.io/cgit/qt/qtmultimedia.git/tree/config.tests/ffmpeg?h=6.11.2

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
