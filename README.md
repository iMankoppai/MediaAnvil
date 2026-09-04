# Sub2LRC

Sub2LRC 是一个 Windows 字幕与 MP3 标签工具，支持将 VTT / SRT 转换为 LRC，也可以把 LRC 歌词和封面写入 MP3，支持中文和批量转换。

![Sub2LRC 软件截图](assets/screenshot.png)

## VTT / SRT 转 LRC

1. 下载并双击运行 `Sub2LRC.exe`。
2. 点击“选择字幕文件”，可以同时选择多个文件。
3. 选择输出目录。
4. 点击“开始批量转换”。
5. 在预览区检查结果，LRC 文件会自动保存到输出目录。

字幕中的多行文字会分别保留，并使用相同的开始时间。已有同名文件时会自动生成 `_1`、`_2` 等新文件，不会覆盖原文件。

## MP3 编辑

1. 切换到“MP3 编辑”页签，只需选择一次歌曲。
2. 程序会读取歌名、歌手、专辑、内嵌歌词和封面并显示预览。
3. 按需修改基础信息、导入或移除歌词、选择或移除封面。
4. 默认使用更安全的“另存为”；也可以主动选择“覆盖原文件”，点击“保存到 MP3”一次完成全部修改。

“取消修改”可以放弃当前尚未保存的全部编辑并恢复刚读取到的内容，不会修改磁盘上的 MP3。

封面图片支持 JPG、JPEG 和 PNG，写入前可以手动裁剪为 1:1。歌词、封面和基础信息的底层格式保持不变；未修改的内容不会重写或删除，音频不会重新编码。覆盖模式先编辑临时副本并校验，成功后才替换原文件；另存为不会修改源文件，程序不会生成 `.bak`。

## 音频转换

1. 切换到“音频转换”页签，选择一个或多个 WAV 文件。
2. 选择 128、192、256 或 320 kbps；默认是 192 kbps。
3. 选择输出目录并点击“开始转换”。

音频编码由内置 FFmpeg 完成，正式发布的单文件 EXE 不需要用户另外安装或配置 FFmpeg。源码运行时也支持系统 `PATH` 或程序同目录的 `ffmpeg.exe`。输出默认保留原文件名并将 `.wav` 改为 `.mp3`；如果同名 MP3 已存在，会生成 `_1`、`_2` 等安全的新文件名。

## 下载 EXE

前往 [Releases](https://github.com/iMankoppai/Sub2LRC/releases/latest) 下载最新版 `Sub2LRC.exe`。目标电脑不需要安装 Python。

## 支持格式

- 输入：`.vtt`、`.srt`
- 输出：`.lrc`
- MP3 内嵌歌词：`.mp3` + `.lrc`
- MP3 内嵌封面：`.mp3` + `.jpg` / `.jpeg` / `.png`
- 音频转换：`.wav` → `.mp3`（需要 FFmpeg）
- 输入编码：UTF-8、UTF-16、GB18030
- 输出编码：带 BOM 的 UTF-8
- 文件名转换示例：`歌曲.wav.vtt` → `歌曲.lrc`

## 已知问题

- Windows 首次运行未签名的 EXE 时，SmartScreen 可能显示“未知发布者”。
- LRC 只保留每段字幕的开始时间，不保留结束时间。
- VTT 的显示控制标签会被移除，因为 LRC 不支持这些标签。
- 歌词写入标准 ID3 `USLT` 标签；个别不读取该标签的播放器可能无法显示。
- PotPlayer 可以读取当前内嵌歌词中的 LRC 时间并同步显示；网易云音乐更适合使用同名外置 LRC。
- 当前版本仅提供 Windows EXE。
- 单文件 EXE 首次启动音频转换时需要短暂解压内置 FFmpeg，因此可能比后续转换稍慢。

## 从源码运行

需要 Python 3.10 或更高版本：

```powershell
python -m pip install -r requirements.txt
python main.py
```

运行测试：

```powershell
python -m unittest discover -s tests -v
```

重新打包：

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```
