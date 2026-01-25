import ctypes
import threading
import time

class StreamProtectController:
    WDA_NONE = 0x00000000
    WDA_EXCLUDEFROMCAPTURE = 0x00000011
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW = 0x00040000
    
    def __init__(self):
        self.is_active = False
        self.initialized = False
        self.update_queue = None
        self.protected_windows = {}
        
        self.user32 = ctypes.windll.user32
        self.SetWindowDisplayAffinity = self.user32.SetWindowDisplayAffinity
        self.GetWindowLongW = self.user32.GetWindowLongW
        self.SetWindowLongW = self.user32.SetWindowLongW
        self.IsWindow = self.user32.IsWindow
        self.FindWindowW = self.user32.FindWindowW

    def set_update_queue(self, queue):
        self.update_queue = queue

    def register_window(self, window_title: str, hwnd: int = None):
        if hwnd is None:
            hwnd = self.FindWindowW(None, window_title)
        if hwnd != 0 and self.IsWindow(hwnd):
            self.protected_windows[window_title] = hwnd
            if self.is_active:
                self._apply_protection(hwnd)
            return True
        return False

    def unregister_window(self, window_title: str):
        if window_title in self.protected_windows:
            hwnd = self.protected_windows[window_title]
            if self.is_active:
                self._remove_protection(hwnd)
            del self.protected_windows[window_title]

    def _apply_protection(self, hwnd: int):
        try:
            self.SetWindowDisplayAffinity(hwnd, self.WDA_EXCLUDEFROMCAPTURE)
            ex_style = self.GetWindowLongW(hwnd, self.GWL_EXSTYLE)
            ex_style |= self.WS_EX_TOOLWINDOW
            ex_style &= ~self.WS_EX_APPWINDOW
            self.SetWindowLongW(hwnd, self.GWL_EXSTYLE, ex_style)
        except Exception:
            pass

    def _remove_protection(self, hwnd: int):
        try:
            self.SetWindowDisplayAffinity(hwnd, self.WDA_NONE)
            ex_style = self.GetWindowLongW(hwnd, self.GWL_EXSTYLE)
            ex_style &= ~self.WS_EX_TOOLWINDOW
            ex_style |= self.WS_EX_APPWINDOW
            self.SetWindowLongW(hwnd, self.GWL_EXSTYLE, ex_style)
        except Exception:
            pass

    def start(self):
        if not self.initialized or self.is_active:
            return False
        for hwnd in self.protected_windows.values():
            if self.IsWindow(hwnd):
                self._apply_protection(hwnd)
        self.is_active = True
        if self.update_queue:
            self.update_queue.put(('status_update', ('streamprotect', "Active (Protected)", '#00e676')))
        return True

    def stop(self):
        if not self.is_active:
            return True
        for hwnd in self.protected_windows.values():
            if self.IsWindow(hwnd):
                self._remove_protection(hwnd)
        self.is_active = False
        if self.update_queue:
            self.update_queue.put(('status_update', ('streamprotect', "Inactive", '#b0b0b0')))
        return True

    def initialize(self):
        if len(self.protected_windows) == 0:
            return False
        self.initialized = True
        print("StreamProtect: initialized")
        return True

    def reset_to_default(self, is_app_closing=False):
        if self.is_active:
            self.stop()
        self.protected_windows.clear()
        self.initialized = False