"""Catch stale local PowerShell commands in source/build instructions."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
DOCUMENTS=('README.md','README.en.md','README-Qt.md','README-Qt.en.md')


def verify(root=ROOT):
    missing=[]
    for name in DOCUMENTS:
        text=(root/name).read_text(encoding='utf8')
        for command in re.findall(r'\.\\([\w\\/.-]+\.ps1)',text):
            if not (root/command.replace('\\','/')).is_file():missing.append(f'{name}: {command}')
    if missing:raise ValueError('Documented scripts do not exist:\n'+'\n'.join(missing))


if __name__=='__main__':
    verify();print('Documented PowerShell commands verified.')
