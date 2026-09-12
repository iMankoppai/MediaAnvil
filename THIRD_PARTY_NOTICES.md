# Third-party notices

## FFmpeg

The standalone Windows build of MediaAnvil includes `ffmpeg.exe` and `ffplay.exe` from the FFmpeg 9.0.1 essentials build published by gyan.dev, one of the Windows build providers linked from the official FFmpeg download page.

- FFmpeg project: https://ffmpeg.org/
- Windows build: https://www.gyan.dev/ffmpeg/builds/
- Corresponding FFmpeg source revision: https://github.com/FFmpeg/FFmpeg/commit/bf1b838f2a
- License information: https://ffmpeg.org/legal.html

The bundled gyan.dev essentials build is distributed under GPLv3. FFmpeg and FFplay are separate executables invoked by MediaAnvil and are not linked into the MediaAnvil Python application.

## ICU

The Qt runtime bundle includes ICU 78.3 for Unicode support. Its license text is included as `licenses/ICU-LICENSE.txt`.

- ICU project: https://icu.unicode.org/
- Source release: https://github.com/unicode-org/icu/releases/tag/release-78.3

## jAudiotagger

The Android client uses the JitPack artifact `com.github.Kaned1as:jaudiotagger:2.3.15` to read and write audio tags for MP3, FLAC, M4A, OGG Vorbis, and Opus. This is the Kaned1as Android-oriented hard fork of jAudiotagger, with additional MP4-DASH and Opus support. It is loaded as a separate Java library by the Android runtime.

- Fork source: https://github.com/Kaned1as/jaudiotagger
- Upstream project: https://www.jthink.net/jaudiotagger/
- License: GNU Lesser General Public License v2.1 or later
- License text: https://github.com/Kaned1as/jaudiotagger/blob/master/license.txt
- JitPack artifact: https://jitpack.io/#Kaned1as/jaudiotagger/2.3.15
