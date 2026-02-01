from turtle import delay
import pymem
import struct
import ctypes
from ctypes import wintypes
import re
import time
import threading
import queue

class ReachController:
    def __init__(self, pm: pymem.Pymem = None):
        self.pm = pm
        self.process_handle = pm.process_handle if pm else None
        self.update_queue = None
        self.should_stop = threading.Event()
        self.is_active = False
        self.initialized = False
        self.reach_address = None
        self.original_reach = 3.0
        self.current_reach = 3.0
        
        self.aob_pattern_str = "00 00 40 40 09 98 44 40 ?? 20 45 40 F7 44 46 40 00 00 00 00 00 00 49 40 DB 0F 49 40 00 00 00 00 26"
        
        self.PAGE_EXECUTE_READWRITE = 0x40
        self.PAGE_READONLY = 0x02
        self.page_size = 0x1000
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.VirtualProtectEx = self.kernel32.VirtualProtectEx
        self.VirtualProtectEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        self.VirtualProtectEx.restype = wintypes.BOOL
        self.WriteProcessMemory = self.kernel32.WriteProcessMemory
        self.WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        self.WriteProcessMemory.restype = wintypes.BOOL

    def set_update_queue(self, update_queue: queue.Queue):
        self.update_queue = update_queue

    def set_pymem_process(self, pm: pymem.Pymem):
        self.pm = pm
        self.process_handle = pm.process_handle

    def update_status(self, message, color):
        if self.update_queue:
            self.update_queue.put(('status_update', ('reach', message, color)))

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
        if not self.reach_address or not self.initialized:
            return False
        if not self.validate_process():
            self.initialized = False
            self.reach_address = None
            return False
        try:
            self.pm.read_bytes(self.reach_address, 4)
            return True
        except Exception:
            self.initialized = False
            self.reach_address = None
            return False

    def pattern_to_regex(self, pattern_str: str):
        bytes_list = pattern_str.split()
        regex_parts = []
        for byte in bytes_list:
            if byte == '??':
                regex_parts.append(b'.')
            else:
                regex_parts.append(re.escape(bytes.fromhex(byte)))
        return b''.join(regex_parts)

    def find_pattern_with_wildcards(self, memory_data: bytes, pattern_str: str):
        regex_pattern = self.pattern_to_regex(pattern_str)
        matches = []
        for match in re.finditer(regex_pattern, memory_data, re.DOTALL):
            matches.append(match.start())
        return matches

    def find_reach_address(self, retries=3, delay=1.0):
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

                matches = self.find_pattern_with_wildcards(bytes_read, self.aob_pattern_str)

                if not matches:
                    time.sleep(delay)
                    continue

                offset = matches[0]
                self.reach_address = base_address + offset

                self.original_reach = struct.unpack('<f', self.pm.read_bytes(self.reach_address, 4))[0]
            
                self.initialized = True

                print(f"Reach: Initialized at 0x{self.reach_address:X}")

                self.update_status("Initialized & Ready", '#00e676')
                return True

            except Exception as e:
                time.sleep(delay)

        self.update_status("Pattern/Memory Init Failed", '#ff5252')
        return False

    def set_reach_value(self, value):
        self.current_reach = float(value)
        if not self.initialized or not self.validate_address():
            return False
        if self.is_active:
            return self._write_reach_to_memory(self.current_reach)
        return True

    def _write_reach_to_memory(self, value):
        if not self.reach_address or not self.validate_address():
            return False
        try:
            reach_data = struct.pack('<f', value)
            page_address = self.reach_address & ~(self.page_size - 1)
            old_protect = wintypes.DWORD(0)
            success = self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(page_address),
                                            self.page_size, self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect))
            if not success:
                return False
            try:
                self.pm.write_bytes(self.reach_address, reach_data, 4)
            except Exception:
                bytes_written = ctypes.c_size_t(0)
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.reach_address),
                                       reach_data, len(reach_data), ctypes.byref(bytes_written))
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(page_address),
                                  self.page_size, old_protect, ctypes.byref(wintypes.DWORD(0)))
            self.update_status(f"Active (Reach: {value:.2f})", '#00e676')
            return True
        except Exception as e:
            self.update_status(f"Write Error: {e.__class__.__name__}", '#ff5252')
            return False

    def enable_reach(self):
        if not self.initialized or not self.validate_address():
            if not self.find_reach_address():
                return False
        if self.is_active:
            return True
        try:
            if self._write_reach_to_memory(self.current_reach):
                self.is_active = True
                self.update_status(f"Active (Reach: {self.current_reach:.2f})", '#00e676')
                return True
            return False
        except Exception as e:
            self.update_status(f"Enable Error: {e.__class__.__name__}", '#ff5252')
            return False

    def disable_reach(self):
        if not self.initialized or not self.is_active:
            return True
        try:
            if self._write_reach_to_memory(self.original_reach):
                self.is_active = False
                self.update_status("Inactive", '#b0b0b0')
                return True
            return False
        except Exception as e:
            self.update_status(f"Disable Error: {e.__class__.__name__}", '#ff5252')
            return False

    def reset_to_default(self, is_app_closing=False):
        if not self.validate_process():
            self.is_active = False
            self.initialized = False
            self.reach_address = None
            self.update_status("Process closed. Reset.", '#b0b0b0')
            return True
        try:
            if is_app_closing and self.reach_address and self.initialized:
                self._write_reach_to_memory(self.original_reach)
                time.sleep(0.05)
            elif self.is_active:
                self.disable_reach()
            self.reach_address = None
            self.initialized = False
            self.is_active = False
            self.current_reach = self.original_reach
            self.update_status("Inactive", '#b0b0b0')
            return True
        except Exception as e:
            self.update_status(f"Reset Error: {e.__class__.__name__}", '#ff5252')
            return False

    def toggle(self):
        if not self.is_active:
            self.enable_reach()
        else:
            self.disable_reach()

    def start(self):
        return self.enable_reach()

    def stop(self, is_app_closing=False):
        self.should_stop.set()
        if is_app_closing:
            self.reset_to_default(is_app_closing=True)
        else:
            self.disable_reach()
        return True

    def initialize(self):
        return self.find_reach_address()