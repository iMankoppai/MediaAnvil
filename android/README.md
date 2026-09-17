# MediaAnvil Android

MediaAnvil Android 是面向本地 ASMR、广播剧、有声内容和音乐文件的专用播放器。它与 Windows 版各司其职：Android 负责随时播放，只保留歌名和歌手两项轻量标签编辑；完整的标签处理、封面处理、音频剪辑和格式转换由 Windows 版完成。

## 当前功能

- 获得存储访问权限后，自动扫描设备中的 MP3、WAV、FLAC、M4A、AAC、OGG 和 Opus，并缓存媒体库以便快速启动。
- 媒体页提供歌曲与自定义分组，支持搜索、排序和仅从播放器中移除歌曲（不会删除原文件）。
- 使用 Media3 ExoPlayer 播放本地音频，支持播放队列、上一首/下一首、随机、列表循环和单曲循环。
- 播放页支持 0.75×–3× 变速、A-B 循环、可配置快退/快进、进度拖动、封面与同步歌词；长按封面约两秒可为当前歌曲选择持久保存的自定义图片。
- 通过歌曲右侧菜单编辑歌名和歌手（MP3、WAV、FLAC、M4A、OGG/Vorbis、Opus）。原始 AAC 在手机端保持只读。
- 自动匹配同名及双后缀 LRC、SRT、VTT 外挂歌词，支持 UTF-8、UTF-16 和 GB18030；没有本地歌词时可从 LRCLIB 搜索同步歌词。候选必须先打开完整歌词与时间轴预览，明确确认后才保存为同目录 LRC。已有歌词可重新搜索替换、选择本地文件、按 0.5 秒调整时间偏移或确认后删除。
- 相同时间戳的原文与译文会合并为双行同步显示；Android 版本身不进行语音识别或机器翻译。
- 支持后台播放、锁屏控制、系统媒体通知和可配置的耳机双击动作。
- 提供睡眠定时和后台播放电池设置入口。
- 设置页可检查 GitHub Releases 中的新版本，并可导出、恢复分组、已移除歌曲、自定义封面关联、歌词偏移和播放器设置。
- 支持简体中文与英文以及深色/浅色主题。

音频文件不会上传。在线歌词搜索会把当前歌曲的标题和歌手发送给 LRCLIB；选择结果后只在音频旁写入一个外挂 LRC 文件。除用户主动保存的歌名和歌手外，Android 版不会改动音频数据或其他标签。

## 界面结构

- **媒体**：浏览、搜索、分组和选择歌曲。
- **播放**：独立的一级播放页面，显示封面、歌词、进度、播放模式和队列。
- **设置**：仅保留与播放器、歌词显示、声音、主题和媒体库扫描相关的选项。

## 与 Windows 版的分工

以下功能只保留在 Windows 版，不再由 Android 版提供：

- 除手机端菜单中的歌名和歌手编辑外，其他音频标签和封面写入
- 封面裁剪
- 音频剪辑与合并
- 音频、图片、歌词和字幕格式转换
- 批量重命名与智能匹配写入

## 本地构建

需要 JDK 17、Android SDK 36（Build Tools 36.0.0）和 Gradle 9.6：

```text
cd android
gradle :app:testDebugUnitTest :app:assembleDebug
```

调试 APK 位于：

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

## 长期签名与发布

将 `signing.properties.example` 复制为 `signing.properties`，填写长期保存的 JKS 路径、密码和别名后运行：

```text
gradle :app:testReleaseUnitTest :app:lintRelease :app:assembleRelease
```

真实的 `signing.properties`、JKS 和密码均不得提交。GitHub 发布工作流使用以下仓库 Secrets 构建同一签名的 Android APK，并将 APK 与 SHA-256 一起加入 Release：

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

## 主要技术

- Kotlin 2.3.21
- Jetpack Compose BOM 2025.08.00
- Android Gradle Plugin 9.4.0
- Media3 1.11.0
- minSdk 26 / targetSdk 36
