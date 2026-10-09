"""Sample working-set memory for this process and its child processes."""
import ctypes
from ctypes import wintypes
import os


def process_tree_mib():
    if os.name!='nt':return None
    class ProcessEntry(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),
            ('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),
            ('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),('exe',wintypes.WCHAR*260)]
    class MemoryCounters(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('faults',wintypes.DWORD),
            *[(name,ctypes.c_size_t) for name in ('peak','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD];kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(ProcessEntry)];kernel.Process32FirstW.restype=wintypes.BOOL
    kernel.Process32NextW.argtypes=kernel.Process32FirstW.argtypes;kernel.Process32NextW.restype=wintypes.BOOL
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(MemoryCounters),wintypes.DWORD];psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    snapshot=kernel.CreateToolhelp32Snapshot(2,0)
    if snapshot==ctypes.c_void_p(-1).value:return None
    entries={};entry=ProcessEntry();entry.size=ctypes.sizeof(entry)
    try:
        valid=kernel.Process32FirstW(snapshot,ctypes.byref(entry))
        while valid:
            entries[entry.pid]=entry.parent;valid=kernel.Process32NextW(snapshot,ctypes.byref(entry))
    finally:kernel.CloseHandle(snapshot)
    selected={os.getpid()}
    while True:
        children={pid for pid,parent in entries.items() if parent in selected}
        if children<=selected:break
        selected.update(children)
    total=0
    for pid in selected:
        handle=kernel.OpenProcess(0x410,False,pid)
        if not handle:continue
        try:
            counters=MemoryCounters();counters.size=ctypes.sizeof(counters)
            if psapi.GetProcessMemoryInfo(handle,ctypes.byref(counters),counters.size):total+=counters.working
        finally:kernel.CloseHandle(handle)
    return total/1024/1024 if total else None
