"""Prevent two desktop copies from opening a camera service simultaneously."""
import contextlib,ctypes,os
@contextlib.contextmanager
def usb_lock():
    if os.name!='nt':raise RuntimeError('实机 USB 操作仅支持 Windows')
    from ctypes import wintypes
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR];k.CreateMutexW.restype=wintypes.HANDLE
    k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];k.WaitForSingleObject.restype=wintypes.DWORD
    k.ReleaseMutex.argtypes=[wintypes.HANDLE];k.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=k.CreateMutexW(None,False,'Local\\A7R3CreativeStudioUSB-v1')
    if not handle:raise RuntimeError('无法创建相机独占锁')
    acquired=False
    try:
        result=k.WaitForSingleObject(handle,0)
        if result not in (0,0x80):raise RuntimeError('另一份 Creative Studio 正在使用相机，请等待它退出会话')
        acquired=True
        if result==0x80:raise RuntimeError('上次相机会话意外结束；请检查相机状态后重新操作')
        yield
    finally:
        if acquired:k.ReleaseMutex(handle)
        k.CloseHandle(handle)
