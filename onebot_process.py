"""Run only the owned NapCat process tree, without a console window."""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import os
import subprocess


class _StartupInfo(ctypes.Structure):
    _fields_ = [('cb', w.DWORD), ('lpReserved', w.LPWSTR), ('lpDesktop', w.LPWSTR),
                ('lpTitle', w.LPWSTR), ('dwX', w.DWORD), ('dwY', w.DWORD),
                ('dwXSize', w.DWORD), ('dwYSize', w.DWORD), ('dwXCountChars', w.DWORD),
                ('dwYCountChars', w.DWORD), ('dwFillAttribute', w.DWORD),
                ('dwFlags', w.DWORD), ('wShowWindow', w.WORD), ('cbReserved2', w.WORD),
                ('lpReserved2', ctypes.c_void_p), ('hStdInput', w.HANDLE),
                ('hStdOutput', w.HANDLE), ('hStdError', w.HANDLE)]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [('hProcess', w.HANDLE), ('hThread', w.HANDLE),
                ('dwProcessId', w.DWORD), ('dwThreadId', w.DWORD)]


class _BasicLimits(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong),
                ('PerJobUserTimeLimit', ctypes.c_longlong), ('LimitFlags', w.DWORD),
                ('MinimumWorkingSetSize', ctypes.c_size_t), ('MaximumWorkingSetSize', ctypes.c_size_t),
                ('ActiveProcessLimit', w.DWORD), ('Affinity', ctypes.c_size_t),
                ('PriorityClass', w.DWORD), ('SchedulingClass', w.DWORD)]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in
                ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', _BasicLimits), ('IoInfo', _IoCounters),
                ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]


class _Accounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_longlong) for name in
                ('TotalUserTime', 'TotalKernelTime', 'ThisPeriodTotalUserTime', 'ThisPeriodTotalKernelTime')]
    _fields_ += [(name, w.DWORD) for name in
                 ('TotalPageFaultCount', 'TotalProcesses', 'ActiveProcesses', 'TotalTerminatedProcesses')]


class OneBotProcess:
    """Assign the suspended launcher to a kill-on-close Job before it can spawn QQ."""

    def __init__(self, command, cwd, environment):
        if os.name != 'nt':
            raise RuntimeError('内置 OneBot 目前支持 Windows。')
        import msvcrt
        self.job = None
        self.process = None
        self.output = None
        self.kernel = k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        k.CreateJobObjectW.restype = w.HANDLE
        k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        k.SetInformationJobObject.restype = w.BOOL
        k.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
        k.QueryInformationJobObject.restype = w.BOOL
        k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        k.AssignProcessToJobObject.restype = w.BOOL
        k.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
        k.TerminateJobObject.restype = w.BOOL
        k.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
        k.CloseHandle.argtypes = [w.HANDLE]
        k.CloseHandle.restype = w.BOOL
        k.ResumeThread.argtypes = [w.HANDLE]
        k.ResumeThread.restype = w.DWORD
        k.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                                     w.BOOL, w.DWORD, ctypes.c_void_p, w.LPCWSTR,
                                     ctypes.POINTER(_StartupInfo), ctypes.POINTER(_ProcessInfo)]
        k.CreateProcessW.restype = w.BOOL
        self.job = k.CreateJobObjectW(None, None)
        if not self.job:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error
        read_fd, write_fd = os.pipe()
        input_fd = os.open(os.devnull, os.O_RDONLY)
        info = _ProcessInfo()
        try:
            os.set_inheritable(write_fd, True)
            os.set_inheritable(input_fd, True)
            startup = _StartupInfo()
            startup.cb = ctypes.sizeof(startup)
            startup.dwFlags = 0x100 | 1  # STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            startup.hStdInput = msvcrt.get_osfhandle(input_fd)
            startup.hStdOutput = startup.hStdError = msvcrt.get_osfhandle(write_fd)
            env_block = ctypes.create_unicode_buffer('\0'.join(
                f'{key}={value}' for key, value in sorted(environment.items(), key=lambda row: row[0].upper())) + '\0\0')
            flags = 0x08000000 | 0x00000004 | 0x00000400  # NO_WINDOW | SUSPENDED | UNICODE_ENVIRONMENT
            if not k.CreateProcessW(str(command[0]), ctypes.create_unicode_buffer(subprocess.list2cmdline(command)),
                                    None, None, True, flags, env_block, str(cwd),
                                    ctypes.byref(startup), ctypes.byref(info)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.process = info.hProcess
            self.pid = info.dwProcessId
            if not k.AssignProcessToJobObject(self.job, self.process):
                error = ctypes.WinError(ctypes.get_last_error())
                k.TerminateProcess(self.process, 1)
                raise RuntimeError('无法托管 OneBot 进程，已取消启动：' + str(error))
            if k.ResumeThread(info.hThread) == 0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
            self.output = os.fdopen(read_fd, 'rb', buffering=0)
            read_fd = None
        except BaseException:
            self.close()
            raise
        finally:
            if info.hThread:
                k.CloseHandle(info.hThread)
            os.close(write_fd)
            os.close(input_fd)
            if read_fd is not None:
                os.close(read_fd)

    def active(self):
        info = _Accounting()
        if not self.job:
            return False
        if not self.kernel.QueryInformationJobObject(self.job, 1, ctypes.byref(info), ctypes.sizeof(info), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return info.ActiveProcesses > 0

    def close(self):
        if self.job:
            self.kernel.TerminateJobObject(self.job, 0)
            self.kernel.CloseHandle(self.job)
            self.job = None
        if self.process:
            self.kernel.CloseHandle(self.process)
            self.process = None
