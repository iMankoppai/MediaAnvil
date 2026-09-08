from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QSpinBox, QDoubleSpinBox, QFrame, QLabel,
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QSizePolicy, QGridLayout,
    QComboBox)
from .common import Page, combo, OutputPath, button
from .design import icon, Toggle
from core.settings import default_settings, save_settings


class SettingSection(QFrame):
    """A settings card with the same visual hierarchy as the tool pages."""
    def __init__(self, symbol, title, description):
        super().__init__(); self.setObjectName('card')
        self.search_text = title + description
        self.outer = QVBoxLayout(self); self.outer.setContentsMargins(14, 8, 14, 8); self.outer.setSpacing(4)
        self.caption = QWidget(); caption = QHBoxLayout(self.caption)
        caption.setContentsMargins(0, 0, 0, 0); caption.setSpacing(9)
        badge = QLabel(); badge.setObjectName('iconBadge'); badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter); badge.setPixmap(icon(symbol, '#2c72f8').pixmap(22, 22))
        caption.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        words = QVBoxLayout(); words.setContentsMargins(0, 0, 0, 0); words.setSpacing(1)
        heading = QLabel(title); heading.setObjectName('sectionTitle'); words.addWidget(heading)
        self.detail = QLabel(description); self.detail.setObjectName('muted'); self.detail.setWordWrap(True); words.addWidget(self.detail)
        caption.addLayout(words, 1); self.outer.addWidget(self.caption)
        body = QWidget(); self.fields = QFormLayout(body); self.fields.setContentsMargins(0, 0, 0, 0)
        self.fields.setHorizontalSpacing(14); self.fields.setVerticalSpacing(1)
        self.fields.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.fields.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.fields.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self.outer.addWidget(body, 1)

    def add(self, label, widget):
        text = QLabel(label); text.setMinimumWidth(128)
        self.fields.addRow(text, widget); self.search_text += label


def aligned_control(control, unit=''):
    host = QWidget(); layout = QHBoxLayout(host); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(8)
    layout.addStretch(1); layout.addWidget(control)
    if unit: layout.addWidget(QLabel(unit))
    return host


class SettingsPage(Page):
    def __init__(self, app):
        super().__init__(app, '设置', '调整应用程序的常用选项')
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.controls = {}; self.sections = []; self.layout.setSpacing(10)
        self.page_detail = next(label for label in self.header.findChildren(QLabel) if label.objectName() == 'muted')
        self.page_badge = next(label for label in self.header.findChildren(QLabel) if label.objectName() == 'pageBadge')

        self.section_host = QWidget(); self.section_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.section_grid = QGridLayout(self.section_host); self.section_grid.setContentsMargins(0, 0, 0, 0)
        self.section_grid.setHorizontalSpacing(10); self.section_grid.setVerticalSpacing(10)
        self.section_grid.setColumnStretch(0, 1); self.section_grid.setColumnStretch(1, 1)
        self.layout.addWidget(self.section_host)

        general = self.section('folder', '常规', '应用的基本行为设置', 0, 0)
        output = combo([('跟随源文件', 'source'), ('指定文件夹', 'custom')]); output.setMaximumWidth(16777215)
        self.controls['default_output_location'] = output
        self.directory = OutputPath(); self.directory.edit.setPlaceholderText('选择默认输出文件夹')
        general.add('默认输出位置', output); general.add('指定目录', self.directory)
        output.currentIndexChanged.connect(lambda: (general.fields.setRowVisible(self.directory, output.currentData() == 'custom'), QTimer.singleShot(0, self.refresh_height)))
        mode = combo([('另存为（推荐）', 'save_as'), ('覆盖原文件', 'overwrite')]); mode.setMaximumWidth(16777215)
        self.controls['default_save_mode'] = mode; general.add('默认保存方式', mode)
        self.language = combo([('简体中文', 'zh_CN'), ('English', 'en_US')]); self.language.setMaximumWidth(16777215)
        self.controls['language'] = self.language
        general.add('语言', self.language); self.general_section = general

        audio = self.section('music', '音频转换', '设置音频格式转换的默认参数', 0, 1)
        for key, label, values in [('default_mp3_bitrate', '默认 MP3 码率', [128, 192, 256, 320]),
                                   ('default_aac_bitrate', '默认 AAC / M4A 码率', [96, 128, 192, 256])]:
            control = combo(values); control.setMinimumWidth(90); control.setMaximumWidth(145); self.controls[key] = control
            audio.add(label, aligned_control(control, 'kbps'))
        self.switch(audio, 'default_keep_sample_rate', '默认保持原采样率')
        self.switch(audio, 'default_keep_channels', '默认保持原声道')
        self.switch(audio, 'default_preserve_metadata', '保留音频元数据（标签信息）')

        image = self.section('image', '图片转换', '设置图片格式转换的默认参数', 1, 0)
        self.number(image, 'default_image_quality', '默认 JPG 质量', 1, 100, '%')
        self.number(image, 'default_webp_quality', '默认 WebP 质量', 1, 100, '%')
        self.switch(image, 'default_keep_image_size', '保持原始尺寸')
        self.image_note = QLabel('不缩放图片，输出与原图相同的尺寸'); self.image_note.setObjectName('muted'); self.image_note.setAlignment(Qt.AlignmentFlag.AlignRight)
        image.outer.addWidget(self.image_note)

        lyrics = self.section('list', '歌词与预览', '设置歌词处理和音频预览的默认参数', 1, 1)
        duration = QDoubleSpinBox(); duration.setRange(.1, 3600); duration.setDecimals(1); duration.setMinimumWidth(90); duration.setMaximumWidth(145)
        self.controls['subtitle_final_duration'] = duration
        lyrics.add('LRC 最后一句持续时间', aligned_control(duration, '秒'))
        self.number(lyrics, 'default_volume', '默认音量', 0, 100, '%')
        self.switch(lyrics, 'auto_load_same_name_lyrics', '自动加载同名歌词')
        self.switch(lyrics, 'prefer_embedded_mp3_lyrics', '优先使用 MP3 内嵌歌词')

        scan = self.section('folder', '文件扫描', '扫描文件时的默认行为', 2, 0, 2)
        self.switch(scan, 'include_subfolders', '包含子文件夹')
        self.layout.addStretch(1)
        self.footer = QWidget(); footer = QHBoxLayout(self.footer); footer.setContentsMargins(0, 0, 0, 0); footer.setSpacing(10)
        self.footer_note = QLabel('ⓘ  修改设置后将自动应用到后续任务'); self.footer_note.setObjectName('muted')
        footer.addWidget(self.footer_note); footer.addStretch()
        footer.addWidget(button('恢复默认设置', self.defaults, symbol='undo'))
        footer.addWidget(button('保存设置', self.save, True, 'save'))
        self.layout.addWidget(self.footer)
        self.populate(app.settings)
        general.fields.setRowVisible(self.directory, output.currentData() == 'custom')
        QTimer.singleShot(0, self._update_responsive_layout)

    def section(self, symbol, title, description, row_index, column, column_span=1):
        section = SettingSection(symbol, title, description); self.sections.append(section)
        section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.section_grid.addWidget(section, row_index, column, 1, column_span)
        return section

    def switch(self, section, key, label, hint=''):
        control = Toggle(label); self.controls[key] = control
        section.add(label, aligned_control(control)); section.search_text += hint

    def number(self, section, key, label, low, high, unit=''):
        control = QSpinBox(); control.setRange(low, high); control.setMinimumWidth(90); control.setMaximumWidth(145)
        self.controls[key] = control; section.add(label, aligned_control(control, unit))

    def refresh_height(self):
        self.setMaximumHeight(16777215); self.section_grid.activate()
        self.section_host.setFixedHeight(self.section_host.sizeHint().height()); self.layout.activate()
        self.setMaximumHeight(self.sizeHint().height())

    def resizeEvent(self, event):
        super().resizeEvent(event); self._update_responsive_layout()

    def showEvent(self, event):
        super().showEvent(event); self._update_responsive_layout(); QTimer.singleShot(0, self._update_responsive_layout)

    def _update_responsive_layout(self):
        viewport = getattr(self, 'scroll', None)
        available = viewport.viewport().size() if viewport and viewport.viewport().height() > 100 else self.size()
        roomy = available.height() >= 590 and available.width() >= 850
        self.layout.setContentsMargins(20, 12, 20, 16) if roomy else self.layout.setContentsMargins(20, 3, 20, 0)
        self.section_grid.setVerticalSpacing(10 if roomy else 3)
        self.page_badge.setVisible(roomy)
        self.page_detail.setVisible(roomy)
        self.image_note.setVisible(roomy)
        self.general_section.fields.setRowVisible(self.language, True)
        for section in self.sections:
            section.detail.setVisible(roomy)
            section.outer.setContentsMargins(16, 8, 16, 8) if roomy else section.outer.setContentsMargins(12, 3, 12, 3)
            badge = next(label for label in section.caption.findChildren(QLabel) if label.objectName() == 'iconBadge')
            badge.setFixedSize(38, 38) if roomy else badge.setFixedSize(30, 30)
        for control in self.controls.values():
            if isinstance(control, Toggle): control.setFixedSize(44, 26)
            elif isinstance(control, (QComboBox, QSpinBox, QDoubleSpinBox)): control.setFixedHeight(32 if roomy else 26)
        QTimer.singleShot(0, self.refresh_height)

    def populate(self, values):
        for key, control in self.controls.items():
            if isinstance(control, QCheckBox): control.setChecked(values[key])
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)): control.setValue(values[key])
            elif isinstance(control, QComboBox): control.setCurrentIndex(max(0, control.findData(values[key])))
        self.directory.edit.setText(values['default_output_directory'])

    def defaults(self): self.populate(default_settings())

    def save(self):
        values = dict(self.app.settings)
        for key, control in self.controls.items():
            values[key] = control.isChecked() if isinstance(control, QCheckBox) else control.value() if isinstance(control, (QSpinBox, QDoubleSpinBox)) else control.currentData()
        values['default_output_directory'] = self.directory.text()
        if values['default_output_location'] == 'custom' and not values['default_output_directory']: return self.app.inform('请选择自定义输出文件夹。')
        try: save_settings(values, self.app.settings_file)
        except Exception as exc: return self.app.inform('保存失败：' + str(exc))
        self.app.settings = values; self.app.apply_defaults(); self.app.set_language(values['language'])
        self.app.statusBar().showMessage(self.app.t('设置已保存并应用'))
