# Sub2LRC

Sub2LRC 是一个 Windows 字幕转歌词工具，支持将 VTT / SRT 转换为 LRC，支持中文和批量转换。

![Sub2LRC 软件截图](assets/screenshot.png)

## 使用方法

1. 下载并双击运行 `Sub2LRC.exe`。
2. 点击“选择字幕文件”，可以同时选择多个文件。
3. 选择输出目录。
4. 点击“开始批量转换”。
5. 在预览区检查结果，LRC 文件会自动保存到输出目录。

字幕中的多行文字会分别保留，并使用相同的开始时间。已有同名文件时会自动生成 `_1`、`_2` 等新文件，不会覆盖原文件。

## 下载 EXE

前往 [Releases](https://github.com/iMankoppai/Sub2LRC/releases/latest) 下载最新版 `Sub2LRC.exe`。目标电脑不需要安装 Python。

## 支持格式

- 输入：`.vtt`、`.srt`
- 输出：`.lrc`
- 输入编码：UTF-8、UTF-16、GB18030
- 输出编码：带 BOM 的 UTF-8
- 文件名转换示例：`歌曲.wav.vtt` → `歌曲.lrc`

## 已知问题

- Windows 首次运行未签名的 EXE 时，SmartScreen 可能显示“未知发布者”。
- LRC 只保留每段字幕的开始时间，不保留结束时间。
- VTT 的显示控制标签会被移除，因为 LRC 不支持这些标签。
- 当前版本仅提供 Windows EXE。

## 从源码运行

需要 Python 3.10 或更高版本：

```powershell
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
