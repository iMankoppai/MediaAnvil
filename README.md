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

## MP3 内嵌歌词

1. 切换到“MP3 内嵌歌词”页签。
2. 选择 `.mp3` 歌曲和 `.lrc` 歌词。
3. 点击“写入歌词”。

歌词会写入 MP3 的 ID3 `USLT` 标签；原有标题、歌手、封面及其他应用写入的歌词不会被删除。

点击“移除内嵌歌词”可以删除 MP3 中全部 `USLT` 和 `SYLT` 歌词标签，不会影响封面和其他标签。

写入和移除均可选择“覆盖原文件”或“另存为”。覆盖模式先处理临时副本，校验成功后才替换原文件；另存为模式不会修改源 MP3。程序不生成 `.bak` 文件。

## MP3 内嵌封面

1. 切换到“MP3 内嵌封面”页签。
2. 选择 `.mp3` 歌曲。
3. 选择 JPG、JPEG 或 PNG 图片。
4. 在裁剪窗口拖动黄色正方形，并用滑块调整裁剪范围。
5. 确认裁剪后点击“写入封面”。

封面会写入 MP3 的 ID3 `APIC` 正面封面标签。已有封面会被替换，其他 ID3 标签和音频数据不会改变；原图片不会被覆盖。

点击“移除内嵌封面”可以删除 MP3 中全部 `APIC` 图片标签，不会影响歌词和其他标签。

写入和移除均可选择“覆盖原文件”或“另存为”，不会生成 `.bak` 文件。

## MP3 基础信息

1. 切换到“MP3 信息”页签并选择歌曲。
2. 程序会读取当前歌名、歌手、专辑，并提示是否检测到封面和歌词。
3. 修改需要调整的内容，点击“保存修改”。

基础信息对应 ID3 的 `TIT2`（歌名）、`TPE1`（歌手）和 `TALB`（专辑）标签。保存不会删除已有封面、歌词或其他标签，也不会重新编码音频。清空输入框后保存，会移除对应的基础标签。

## 下载 EXE

前往 [Releases](https://github.com/iMankoppai/Sub2LRC/releases/latest) 下载最新版 `Sub2LRC.exe`。目标电脑不需要安装 Python。

## 支持格式

- 输入：`.vtt`、`.srt`
- 输出：`.lrc`
- MP3 内嵌歌词：`.mp3` + `.lrc`
- MP3 内嵌封面：`.mp3` + `.jpg` / `.jpeg` / `.png`
- 输入编码：UTF-8、UTF-16、GB18030
- 输出编码：带 BOM 的 UTF-8
- 文件名转换示例：`歌曲.wav.vtt` → `歌曲.lrc`

## 已知问题

- Windows 首次运行未签名的 EXE 时，SmartScreen 可能显示“未知发布者”。
- LRC 只保留每段字幕的开始时间，不保留结束时间。
- VTT 的显示控制标签会被移除，因为 LRC 不支持这些标签。
- 歌词写入标准 ID3 `USLT` 标签；个别不读取该标签的播放器可能无法显示。
- 当前版本仅提供 Windows EXE。

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
