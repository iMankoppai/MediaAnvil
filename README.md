# Sub2LRC

Sub2LRC 是一个 Windows 字幕与歌词工具，支持将 VTT / SRT 转换为 LRC，也可以把 LRC 歌词写入 MP3，支持中文和批量转换。

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

歌词会写入 MP3 的 ID3 `USLT` 标签。写入前会在歌曲旁创建 `.bak` 备份；原有标题、歌手、封面及其他应用写入的歌词不会被删除。

## 下载 EXE

前往 [Releases](https://github.com/iMankoppai/Sub2LRC/releases/latest) 下载最新版 `Sub2LRC.exe`。目标电脑不需要安装 Python。

## 支持格式

- 输入：`.vtt`、`.srt`
- 输出：`.lrc`
- MP3 内嵌歌词：`.mp3` + `.lrc`
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
