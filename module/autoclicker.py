import threading
import time
import queue
import ctypes
from ctypes import wintypes
import keyboard
import pygetwindow as gw

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD)
    ]

class _InputUnion(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _InputUnion)
    ]


class AutoClickerController:
    def __init__(self):
        self.update_queue = None
        self.should_stop = threading.Event()
        self.is_active = False
        self.initialized = True
        self.left_cps = 10.0
        self.right_cps = 10.0
        self.left_key = 'z'
        self.right_key = 'x'
        self.left_enabled = True
        self.right_enabled = True
        self.left_thread = None
        self.right_thread = None
        self.monitor_thread = None
        self.left_key_pressed = False
        self.right_key_pressed = False
        self._state_lock = threading.Lock()
        self.minecraft_active = False
        self.target_process_name = "Minecraft"
        self.user32 = ctypes.windll.user32

    def set_update_queue(self, update_queue: queue.Queue):
        self.update_queue = update_queue

    def update_status(self, message, color):
        if self.update_queue:
            self.update_queue.put(('status_update', ('autoclicker', message, color)))

    def set_cps(self, left_cps: float, right_cps: float):
        with self._state_lock:
            self.left_cps = max(1.0, min(20.0, left_cps))
            self.right_cps = max(1.0, min(20.0, right_cps))

    def set_keybinds(self, left_key: str, right_key: str):
        with self._state_lock:
            self.left_key = left_key.lower()
            self.right_key = right_key.lower()

    def set_click_enabled(self, left_enabled: bool, right_enabled: bool):
        with self._state_lock:
            self.left_enabled = left_enabled
            self.right_enabled = right_enabled

    def _is_minecraft_active(self):
        try:
            active_window = gw.getActiveWindow()
            if active_window is None:
                return False
            window_title = active_window.title
            return self.target_process_name in window_title
        except Exception as e:
            return False

    def _monitor_minecraft_status(self):
        while not self.should_stop.is_set():
            try:
                is_active = self._is_minecraft_active()
                with self._state_lock:
                    self.minecraft_active = is_active
                time.sleep(0.1)
            except Exception as e:
                time.sleep(0.1)

    def _send_mouse_input(self, flags):
        extra = ctypes.c_ulong(0)
        ii_ = _InputUnion()
        ii_.mi = MOUSEINPUT(0, 0, 0, flags, 0, ctypes.pointer(extra))
        x = INPUT(INPUT_MOUSE, ii_)
        result = self.user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))
        return result == 1

    def _left_click(self):
        if not self._send_mouse_input(MOUSEEVENTF_LEFTDOWN):
            return False
        time.sleep(0.01)
        if not self._send_mouse_input(MOUSEEVENTF_LEFTUP):
            return False
        return True

    def _right_click(self):
        if not self._send_mouse_input(MOUSEEVENTF_RIGHTDOWN):
            return False
        time.sleep(0.01)
        if not self._send_mouse_input(MOUSEEVENTF_RIGHTUP):
            return False
        return True

    def _left_click_loop(self):
        last_click_time = 0
        while not self.should_stop.is_set():
            try:
                with self._state_lock:
                    key = self.left_key
                    enabled = self.left_enabled
                    cps = self.left_cps
                    minecraft_active = self.minecraft_active
                if not minecraft_active:
                    time.sleep(0.1)
                    continue
                is_pressed = keyboard.is_pressed(key)
                if is_pressed and enabled:
                    current_time = time.perf_counter()
                    interval = 1.0 / cps
                    if current_time - last_click_time >= interval:
                        self._left_click()
                        last_click_time = current_time
                    else:
                        remaining = interval - (current_time - last_click_time)
                        if remaining > 0:
                            time.sleep(min(remaining, 0.01))
                else:
                    time.sleep(0.001)
            except Exception as e:
                time.sleep(0.01)

    def _right_click_loop(self):
        last_click_time = 0
        while not self.should_stop.is_set():
            try:
                with self._state_lock:
                    key = self.right_key
                    enabled = self.right_enabled
                    cps = self.right_cps
                    minecraft_active = self.minecraft_active
                if not minecraft_active:
                    time.sleep(0.1)
                    continue
                is_pressed = keyboard.is_pressed(key)
                if is_pressed and enabled:
                    current_time = time.perf_counter()
                    interval = 1.0 / cps
                    if current_time - last_click_time >= interval:
                        self._right_click()
                        last_click_time = current_time
                    else:
                        remaining = interval - (current_time - last_click_time)
                        if remaining > 0:
                            time.sleep(min(remaining, 0.01))
                else:
                    time.sleep(0.001)
            except Exception as e:
                time.sleep(0.01)

    def start(self):
        if self.is_active:
            return True
        try:
            self.should_stop.clear()
            with self._state_lock:
                self.left_key_pressed = False
                self.right_key_pressed = False
                self.minecraft_active = False
            self.monitor_thread = threading.Thread(target=self._monitor_minecraft_status, daemon=True)
            self.monitor_thread.start()
            self.left_thread = threading.Thread(target=self._left_click_loop, daemon=True)
            self.right_thread = threading.Thread(target=self._right_click_loop, daemon=True)        
            self.left_thread.start()
            self.right_thread.start()
            self.is_active = True          
            with self._state_lock:
                left_display = self.left_key.upper()
                right_display = self.right_key.upper()
            self.update_status(f"Active (L:{left_display} R:{right_display})", '#00e676')
            return True
        except Exception as e:
            self.update_status(f"Start Error: {e.__class__.__name__}", '#ff5252')
            return False

    def stop(self, is_app_closing=False):
        if not self.is_active:
            return True
        try:
            self.should_stop.set()
            with self._state_lock:
                self.left_key_pressed = False
                self.right_key_pressed = False
                self.minecraft_active = False
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=2.0)
            if self.left_thread and self.left_thread.is_alive():
                self.left_thread.join(timeout=2.0)
            if self.right_thread and self.right_thread.is_alive():
                self.right_thread.join(timeout=2.0)
            self.is_active = False
            self.update_status("Inactive", '#b0b0b0')
            return True
        except Exception as e:
            self.update_status(f"Stop Error: {e.__class__.__name__}", '#ff5252')
            return False

    def toggle(self):
        if self.is_active:
            return self.stop()
        else:
            return self.start()

    def reset_to_default(self, is_app_closing=False):
        self.stop(is_app_closing=is_app_closing)
        with self._state_lock:
            self.left_key_pressed = False
            self.right_key_pressed = False
            self.minecraft_active = False
        return True

    def validate_process(self):
        return True

    def initialize(self):
        print("AutoClicker: Initialized")
        return True