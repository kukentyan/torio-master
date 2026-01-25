import pymem
import struct
import ctypes
from ctypes import wintypes
import re
import time
import threading
import queue
import keyboard

class SprintController:
    def __init__(self, pm: pymem.Pymem = None):
        self.pm = pm
        self.process_handle = pm.process_handle if pm else None
        self.update_queue = None
        self.should_stop = threading.Event()
        self.is_active = False
        self.is_sprinting = False
        self.initialized = False
        self.sprint_addr1 = None
        self.sprint_newmem1 = None
        self.sprint_original_bytes1 = None
        self.sprint_addr2 = None
        self.sprint_newmem2 = None
        self.sprint_original_bytes2 = None
        self.sprint_pattern1 = b'\x41\x80\x7B\x17\x00'
        self.sprint_pattern2 = b'\x41\x8B\x03\x33\xC9'
        self.current_key = 'p'
        self.sprint_thread = None
        self.PAGE_EXECUTE_READWRITE = 0x40
        self.MEM_COMMIT = 0x1000
        self.MEM_RESERVE = 0x2000
        self.MEM_RELEASE = 0x8000
        self.page_size = 0x1000
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.VirtualAllocEx = self.kernel32.VirtualAllocEx
        self.VirtualAllocEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
        self.VirtualAllocEx.restype = wintypes.LPVOID
        self.VirtualProtectEx = self.kernel32.VirtualProtectEx
        self.VirtualProtectEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        self.VirtualProtectEx.restype = wintypes.BOOL
        self.WriteProcessMemory = self.kernel32.WriteProcessMemory
        self.WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        self.WriteProcessMemory.restype = wintypes.BOOL
        self.VirtualFreeEx = self.kernel32.VirtualFreeEx
        self.VirtualFreeEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]
        self.VirtualFreeEx.restype = wintypes.BOOL

    def set_update_queue(self, update_queue: queue.Queue):
        self.update_queue = update_queue

    def set_pymem_process(self, pm: pymem.Pymem):
        self.pm = pm
        self.process_handle = pm.process_handle

    def update_status(self, message, color):
        if self.update_queue:
            self.update_queue.put(('status_update', ('sprint', message, color)))

    def validate_process(self):
        try:
            if not self.pm or not self.process_handle:
                return False
            exit_code = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetExitCodeProcess(self.process_handle, ctypes.byref(exit_code)) == 0:
                return False
            return exit_code.value == 259
        except Exception:
            return False

    def validate_address(self):
        if not self.sprint_addr1 or not self.sprint_addr2 or not self.initialized:
            return False
        if not self.validate_process():
            self.initialized = False
            self.sprint_addr1 = None
            self.sprint_addr2 = None
            return False
        try:
            self.pm.read_bytes(self.sprint_addr1, 5)
            self.pm.read_bytes(self.sprint_addr2, 5)
            return True
        except Exception:
            self.initialized = False
            self.sprint_addr1 = None
            self.sprint_addr2 = None
            return False

    def allocate_near(self, base_addr: int, size: int = 0x1000):
        start = base_addr & 0xFFFFFFFFFFFFF000
        offsets = [0]
        for i in range(1, 0x7FFFFF00 // 0x1000):
            offsets.append(i * 0x1000)
            offsets.append(-i * 0x1000)
        for offset in offsets:
            addr = start + offset
            if addr < 0x10000:
                continue
            mem = self.VirtualAllocEx(self.process_handle, ctypes.c_void_p(addr), size,
                                      self.MEM_COMMIT | self.MEM_RESERVE, self.PAGE_EXECUTE_READWRITE)
            if mem:
                return mem
        raise MemoryError("Could not allocate memory near target address")

    def find_sprint_addresses(self, retries=3, delay=1.0):
        if self.initialized and self.validate_address():
            return True
        if not self.validate_process():
            return False
        for attempt in range(retries):
            try:
                base_module = pymem.process.module_from_name(self.process_handle, "Minecraft.Windows.exe")
                if not base_module:
                    time.sleep(delay)
                    continue
                base_address = base_module.lpBaseOfDll
                module_size = base_module.SizeOfImage
                bytes_read = self.pm.read_bytes(base_address, module_size)
                pattern1_matches = [m.start() for m in re.finditer(re.escape(self.sprint_pattern1), bytes_read)]
                pattern2_matches = [m.start() for m in re.finditer(re.escape(self.sprint_pattern2), bytes_read)]
                if not pattern1_matches or not pattern2_matches:
                    time.sleep(delay)
                    continue
                self.sprint_addr1 = base_address + pattern1_matches[0]
                self.sprint_addr2 = base_address + pattern2_matches[0]
                self.sprint_original_bytes1 = self.pm.read_bytes(self.sprint_addr1, 5)
                self.sprint_original_bytes2 = self.pm.read_bytes(self.sprint_addr2, 5)
                self.sprint_newmem1 = self.allocate_near(self.sprint_addr1, 0x100)
                self.sprint_newmem2 = self.allocate_near(self.sprint_addr2, 0x100)
                if not self.sprint_newmem1 or not self.sprint_newmem2:
                    time.sleep(delay)
                    continue
                self.initialized = True
                self.update_status("Initialized & Ready", '#00e676')
                print(f"Sprint: Initialized at 0x{self.sprint_addr1:X} and 0x{self.sprint_addr2:X}")
                return True
            except Exception as e:
                time.sleep(delay)
        self.update_status("Pattern/Memory Init Failed", '#ff5252')
        return False

    def _write_sprint_patches(self):
        if not self.sprint_addr1 or not self.sprint_addr2 or not self.sprint_newmem1 or not self.sprint_newmem2:
            return False
        if not self.validate_address():
            return False
        try:
            patch1_bytes = b'\x90\x90\x90\x90\x90'
            old_protect1 = wintypes.DWORD()
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.sprint_addr1), 5,
                                 self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect1))
            try:
                self.pm.write_bytes(self.sprint_addr1, patch1_bytes, len(patch1_bytes))
            except Exception:
                bytes_written = ctypes.c_size_t()
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.sprint_addr1),
                                       patch1_bytes, len(patch1_bytes), ctypes.byref(bytes_written))
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.sprint_addr1), 5,
                                 old_protect1.value, ctypes.byref(old_protect1))
            patch2_bytes = b'\x90\x90\x90'
            old_protect2 = wintypes.DWORD()
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.sprint_addr2), 3,
                                 self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect2))
            try:
                self.pm.write_bytes(self.sprint_addr2, patch2_bytes, len(patch2_bytes))
            except Exception:
                bytes_written = ctypes.c_size_t()
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.sprint_addr2),
                                       patch2_bytes, len(patch2_bytes), ctypes.byref(bytes_written))
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.sprint_addr2), 3,
                                 old_protect2.value, ctypes.byref(old_protect2))
            return True
        except Exception as e:
            self.update_status(f"Write Error: {e.__class__.__name__}", '#ff5252')
            return False

    def _restore_original_bytes(self):
        try:
            old_protect1 = wintypes.DWORD()
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.sprint_addr1), 5,
                                 self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect1))
            try:
                self.pm.write_bytes(self.sprint_addr1, self.sprint_original_bytes1, len(self.sprint_original_bytes1))
            except Exception:
                bytes_written = ctypes.c_size_t()
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.sprint_addr1),
                                       self.sprint_original_bytes1, len(self.sprint_original_bytes1),
                                       ctypes.byref(bytes_written))     
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.sprint_addr1), 5,
                                 old_protect1.value, ctypes.byref(old_protect1))           
            old_protect2 = wintypes.DWORD()
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.sprint_addr2), 3,
                                 self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect2))            
            try:
                self.pm.write_bytes(self.sprint_addr2, self.sprint_original_bytes2[:3], 3)
            except Exception:
                bytes_written = ctypes.c_size_t()
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.sprint_addr2),
                                       self.sprint_original_bytes2[:3], 3,
                                       ctypes.byref(bytes_written))
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.sprint_addr2), 3,
                                 old_protect2.value, ctypes.byref(old_protect2))
            return True
        except Exception as e:
            return False

    def sprint_loop(self):
        from config import ConfigManager
        config = ConfigManager("config.json")
        if self.update_queue:
            self.update_queue.put(('status_update', ('sprint', f"Active (Not Sprinting) ({self.current_key.upper()})", '#00e676')))
        rescan_delay = 5.0
        last_rescan_time = 0
        last_key_check = 0
        key_check_interval = 0.3       
        while self.is_active and not self.should_stop.is_set():
            current_time = time.time()            
            if current_time - last_key_check >= key_check_interval:
                try:
                    new_key = config.get_keybind("sprint") or "p"
                    if new_key != self.current_key:
                        old_key = self.current_key
                        self.current_key = new_key
                        if self.update_queue:
                            if self.is_sprinting:
                                self.update_queue.put(('status_update', ('sprint', f"Sprinting ({self.current_key.upper()})", '#00e676')))
                            else:
                                self.update_queue.put(('status_update', ('sprint', f"Not Sprinting ({self.current_key.upper()})", '#00e676')))
                except Exception as e:
                    pass
                last_key_check = current_time
            if not self.validate_address():
                if current_time - last_rescan_time >= rescan_delay:
                    if not self.initialize():
                        time.sleep(rescan_delay)
                    last_rescan_time = current_time
                continue
            try:
                if keyboard.is_pressed(self.current_key):
                    if not self.is_sprinting:
                        if self._write_sprint_patches():
                            self.is_sprinting = True
                            if self.update_queue:
                                self.update_queue.put(('status_update', ('sprint', f"Sprinting ({self.current_key.upper()})", '#00e676')))
                    else:
                        if self._restore_original_bytes():
                            self.is_sprinting = False
                            if self.update_queue:
                                self.update_queue.put(('status_update', ('sprint', f"Not Sprinting ({self.current_key.upper()})", '#00e676')))
                    while keyboard.is_pressed(self.current_key) and self.is_active:
                        time.sleep(0.05)
                time.sleep(0.05)
            except Exception as e:
                self.stop()
                break
        if self.is_sprinting:
            self._restore_original_bytes()
            self.is_sprinting = False
        if self.update_queue:
            self.update_queue.put(('status_update', ('sprint', "Inactive", '#b0b0b0')))

    def reset_to_default(self, is_app_closing=False):
        if not self.validate_process():
            self.is_active = False
            self.initialized = False
            self.sprint_addr1 = None
            self.sprint_addr2 = None
            self.update_status("Process closed. Reset.", '#b0b0b0')
            return True
        try:
            if self.is_sprinting:
                self._restore_original_bytes()
                self.is_sprinting = False

            if self.sprint_addr1 and self.sprint_original_bytes1:
                old_protect = wintypes.DWORD()
                self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.sprint_addr1), 5,
                                     self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect))
                try:
                    self.pm.write_bytes(self.sprint_addr1, self.sprint_original_bytes1, len(self.sprint_original_bytes1))
                except Exception:
                    bytes_written = ctypes.c_size_t()
                    self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.sprint_addr1),
                                           self.sprint_original_bytes1, len(self.sprint_original_bytes1),
                                           ctypes.byref(bytes_written))
                self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.sprint_addr1), 5,
                                     old_protect.value, ctypes.byref(old_protect))
            if self.sprint_addr2 and self.sprint_original_bytes2:
                old_protect = wintypes.DWORD()
                self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.sprint_addr2), 3,
                                     self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect))
                try:
                    self.pm.write_bytes(self.sprint_addr2, self.sprint_original_bytes2[:3], 3)
                except Exception:
                    bytes_written = ctypes.c_size_t()
                    self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.sprint_addr2),
                                           self.sprint_original_bytes2[:3], 3,
                                           ctypes.byref(bytes_written))
                self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.sprint_addr2), 3,
                                     old_protect.value, ctypes.byref(old_protect))
            if self.sprint_newmem1:
                self.VirtualFreeEx(self.process_handle, ctypes.c_void_p(self.sprint_newmem1), 0, self.MEM_RELEASE)
                self.sprint_newmem1 = None
            if self.sprint_newmem2:
                self.VirtualFreeEx(self.process_handle, ctypes.c_void_p(self.sprint_newmem2), 0, self.MEM_RELEASE)
                self.sprint_newmem2 = None
            self.sprint_addr1 = None
            self.sprint_addr2 = None
            self.initialized = False
            self.update_status("Inactive", '#b0b0b0')
            return True
        except Exception as e:
            self.update_status(f"Reset Error: {e.__class__.__name__}", '#ff5252')
            return False

    def start(self):
        if not self.is_active:
            if not self.initialize():
                return False
            self.is_active = True
            self.should_stop.clear()
            self.sprint_thread = threading.Thread(target=self.sprint_loop, daemon=True)
            self.sprint_thread.start()
            return True
        return True

    def stop(self, is_app_closing=False):
        if self.is_active:
            self.is_active = False
            self.should_stop.set()
            if self.sprint_thread and self.sprint_thread.is_alive():
                try:
                    self.sprint_thread.join(timeout=1.5)
                except Exception as e:
                    pass
            self.sprint_thread = None
            if self.is_sprinting:
                self._restore_original_bytes()
                self.is_sprinting = False
            
            if is_app_closing:
                self.reset_to_default(is_app_closing=True)
        return True

    def toggle(self):
        if not self.is_active:
            return self.start()
        else:
            return self.stop()

    def initialize(self):
        return self.find_sprint_addresses()