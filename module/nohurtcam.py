import pymem
import struct
import ctypes
from ctypes import wintypes
import re
import time
import threading
import queue


class NoHurtCamController:
    def __init__(self, pm: pymem.Pymem = None):
        self.pm = pm
        self.process_handle = pm.process_handle if pm else None
        self.update_queue = None
        self.should_stop = threading.Event()
        self.is_active = False
        self.initialized = False
        self.inject_addr = None
        self.newmem = None
        self.original_bytes = None
        self.pattern_str = "?? FA 00 48 83 C4 28 C3 F3 0F 10 42 18 48 83 C4 28 C3 CC CC CC CC CC CC CC CC CC CC CC CC CC 48 83 EC 28 48 8B 01 48 8D 54 24 30 41 B8 35 02 00 00 48 8B 40 08 FF 15 ?? ?? ?? ?? 48"
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

    def pattern_to_regex(self, pattern_str):
        bytes_list = pattern_str.split()
        regex_parts = []
        for byte in bytes_list:
            if byte == '??':
                regex_parts.append(b'.')
            else:
                regex_parts.append(re.escape(bytes.fromhex(byte)))
        return b''.join(regex_parts)

    def find_pattern_with_wildcards(self, memory_data, pattern_str):
        regex_pattern = self.pattern_to_regex(pattern_str)
        matches = []
        for match in re.finditer(regex_pattern, memory_data, re.DOTALL):
            matches.append(match.start())
        return matches

    def set_update_queue(self, update_queue: queue.Queue):
        self.update_queue = update_queue

    def set_pymem_process(self, pm: pymem.Pymem):
        self.pm = pm
        self.process_handle = pm.process_handle

    def update_status(self, message, color):
        if self.update_queue:
            self.update_queue.put(('status_update', ('nohurtcam', message, color)))

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
        if not self.inject_addr or not self.initialized:
            return False
        if not self.validate_process():
            self.initialized = False
            self.inject_addr = None
            return False
        try:
            self.pm.read_bytes(self.inject_addr, 13)
            return True
        except Exception:
            self.initialized = False
            self.inject_addr = None
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

    def find_nohurtcam_address(self, retries=3, delay=1.0):
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
                matches = self.find_pattern_with_wildcards(bytes_read, self.pattern_str)
                if not matches:
                    time.sleep(delay)
                    continue
                self.inject_addr = base_address + matches[0] + 8
                self.original_bytes = self.pm.read_bytes(self.inject_addr, 5)
                self.newmem = self.allocate_near(self.inject_addr, 0x1000)
                if not self.newmem:
                    time.sleep(delay)
                    continue

                self.initialized = True
                self.update_status("Initialized & Ready", '#00e676')

                print(f"NoHurtCam: Initialized at 0x{self.inject_addr:X}")

                return True
                
            except Exception:
                time.sleep(delay)
        
        self.update_status("Pattern/Memory Init Failed", '#ff5252')
        return False

    def _write_nohurtcam_patch(self):
        if not self.inject_addr or not self.newmem or not self.validate_address():
            return False
        try:
            shellcode = b'\x0F\x57\xC0'
            return_address = self.inject_addr + 5
            jmp_back = return_address - (self.newmem + len(shellcode) + 5)
            if not -0x80000000 <= jmp_back <= 0x7FFFFFFF:
                return False
            shellcode += b'\xE9' + struct.pack('<i', jmp_back)
            try:
                self.pm.write_bytes(self.newmem, shellcode, len(shellcode))
            except Exception:
                bytes_written = ctypes.c_size_t()
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.newmem),
                                       shellcode, len(shellcode), ctypes.byref(bytes_written))
            jmp_offset = self.newmem - (self.inject_addr + 5)
            if not -0x80000000 <= jmp_offset <= 0x7FFFFFFF:
                return False
            patch_bytes = b'\xE9' + struct.pack('<i', jmp_offset)
            old_protect = wintypes.DWORD()
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.inject_addr), 5,
                                 self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect))
            try:
                self.pm.write_bytes(self.inject_addr, patch_bytes, len(patch_bytes))
            except Exception:
                bytes_written = ctypes.c_size_t()
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.inject_addr),
                                       patch_bytes, len(patch_bytes), ctypes.byref(bytes_written))
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.inject_addr), 5,
                                 old_protect.value, ctypes.byref(old_protect))
            self.update_status("Active", '#00e676')
            return True
        except Exception as e:
            self.update_status(f"Write Error: {e.__class__.__name__}", '#ff5252')
            return False

    def enable_nohurtcam(self):
        if not self.initialized or not self.validate_address():
            if not self.find_nohurtcam_address():
                return False
        if self.is_active:
            return True
        try:
            if not self._write_nohurtcam_patch():
                return False
            self.is_active = True
            self.update_status("Active", '#00e676')
            return True
        except Exception as e:
            self.update_status(f"Enable Error: {e.__class__.__name__}", '#ff5252')
            return False

    def disable_nohurtcam(self):
        if not self.initialized or not self.is_active:
            return True
        try:
            old_protect = wintypes.DWORD()
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.inject_addr), 5,
                                 self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect))
            try:
                self.pm.write_bytes(self.inject_addr, self.original_bytes, len(self.original_bytes))
            except Exception:
                bytes_written = ctypes.c_size_t()
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.inject_addr),
                                       self.original_bytes, len(self.original_bytes),
                                       ctypes.byref(bytes_written))
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.inject_addr), 5,
                                 old_protect.value, ctypes.byref(old_protect))
            self.is_active = False
            self.update_status("Inactive", '#b0b0b0')
            return True
        except Exception as e:
            self.update_status(f"Disable Error: {e.__class__.__name__}", '#ff5252')
            return False

    def reset_to_default(self, is_app_closing=False):
        if not self.validate_process():
            self.is_active = False
            self.initialized = False
            self.inject_addr = None
            self.update_status("Process closed. Reset.", '#b0b0b0')
            return True
        try:
            if self.is_active:
                self.disable_nohurtcam()
            if self.inject_addr and self.original_bytes:
                old_protect = wintypes.DWORD()
                self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.inject_addr), 5,
                                     self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect))
                try:
                    self.pm.write_bytes(self.inject_addr, self.original_bytes, len(self.original_bytes))
                except Exception:
                    bytes_written = ctypes.c_size_t()
                    self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.inject_addr),
                                           self.original_bytes, len(self.original_bytes),
                                           ctypes.byref(bytes_written))
                self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.inject_addr), 5,
                                     old_protect.value, ctypes.byref(old_protect))
            if self.newmem:
                self.VirtualFreeEx(self.process_handle, ctypes.c_void_p(self.newmem), 0, self.MEM_RELEASE)
                self.newmem = None
            self.inject_addr = None
            self.initialized = False
            self.update_status("Inactive", '#b0b0b0')
            return True
        except Exception as e:
            self.update_status(f"Reset Error: {e.__class__.__name__}", '#ff5252')
            return False

    def toggle(self):
        if not self.is_active:
            return self.enable_nohurtcam()
        else:
            return self.disable_nohurtcam()

    def start(self):
        return self.enable_nohurtcam()

    def stop(self, is_app_closing=False):
        self.should_stop.set()
        if is_app_closing:
            self.reset_to_default(is_app_closing=True)
        else:
            self.disable_nohurtcam()
        return True

    def initialize(self):
        return self.find_nohurtcam_address()