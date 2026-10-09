"""Compatibility imports; implementations live in modules grouped by responsibility."""
from pathlib import Path
import sys
from PySide6.QtCore import QStandardPaths as QStandardPaths
from PySide6.QtWidgets import QFileDialog as QFileDialog
from .file_dialogs import dialog_category as dialog_category, dialog_initial_directory as dialog_initial_directory, remember_dialog_selection as remember_dialog_selection, dialog_filters as dialog_filters, remember_dialog_filter as remember_dialog_filter
from .layouts import button as button, row as row, combo as combo, group as group, SegmentedTabs as SegmentedTabs, Columns as Columns, form as form
from .image_widgets import set_picture as set_picture, thumbnail as thumbnail, _thumbnail as _thumbnail
from .table_widgets import StatusDelegate as StatusDelegate, FileDelegate as FileDelegate, ThumbnailDelegate as ThumbnailDelegate, table as table, fill_table as fill_table
from .file_widgets import OutputPath as OutputPath, file_size as file_size, FileList as FileList
from .page import Page as Page
from .workers import TaskReporter as TaskReporter, Worker as Worker
from .sliders import ClickSlider as ClickSlider


def resource(name):
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / name
