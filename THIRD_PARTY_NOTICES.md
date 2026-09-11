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

The Android client uses jAudiotagger 3.0.1 to read and write audio tags (MP3/FLAC/M4A/OGG). jAudiotagger is distributed under the GNU Lesser General Public License v2.1 and is loaded as a separate library by the Android runtime.

- Project: https://www.jthink.net/jaudiotagger/
- Source release: https://bitbucket.org/ijabz/jaudiotagger/src/master/
- Maven Central artifact: https://repo1.maven.org/maven2/net/jthink/jaudiotagger/3.0.1/
- License: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html
