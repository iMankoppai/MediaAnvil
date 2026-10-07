"""Local rename journal, written before each filesystem move."""
from pathlib import Path

from .audio_renamer import RenameRecord
from .persistence import read_json, write_json


def file_identity(path: Path) -> tuple[int, ...]:
    stat=path.stat()
    return stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns


class RenameJournal:
    def __init__(self,path: Path):
        self.path=path;self.current=[];self.previous=[]

    def _validated(self,entries,pending=False):
        if not isinstance(entries,list):return []
        result=[]
        for entry in entries:
            try:
                old=Path(entry['old']);new=Path(entry['new']);identity=entry['identity']
                if not old.is_absolute() or not new.is_absolute() or len(identity)!=4 or not all(isinstance(v,int) for v in identity):continue
                if pending and old.is_file() and file_identity(old)==tuple(identity):
                    # This intent was saved, but the move never happened.
                    if not new.is_file() or file_identity(new)!=tuple(identity):continue
                result.append(entry)
            except (OSError,KeyError,TypeError,ValueError):continue
        return result

    def entries(self):
        value=read_json(self.path,{})
        if not isinstance(value,dict) or value.get('version')!=1:return []
        entries=self._validated(value.get('records',[]),value.get('pending',False))
        if value.get('pending') and not entries:return self._validated(value.get('previous',[]))
        return entries

    def records(self):
        return tuple(RenameRecord(Path(e['old']),Path(e['new'])) for e in self.entries())

    def identities(self):
        return {Path(e['new']):tuple(e['identity']) for e in self.entries()}

    def begin(self):
        self.previous=self.entries();self.current=[]
        self._save_pending()

    def _save_pending(self):
        write_json(self.path,{'version':1,'pending':True,'previous':self.previous,'records':self.current})

    def prepare(self,record):
        self.current.append({'old':str(record.old_path.resolve()),'new':str(record.new_path.resolve()),
                             'identity':file_identity(record.old_path)})
        self._save_pending()

    def finish(self):
        write_json(self.path,{'version':1,'records':self.entries()})

    def restored(self,record):
        entries=[e for e in self.entries() if Path(e['old'])!=record.old_path or Path(e['new'])!=record.new_path]
        write_json(self.path,{'version':1,'records':entries})
