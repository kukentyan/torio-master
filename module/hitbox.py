import pymem
import struct
import ctypes
from ctypes import wintypes
import re
import time
import threading
import queue


class HitboxController:
    def __init__(self, pm: pymem.Pymem = None, version_config: dict = None):
        self.pm = pm
        self.process_handle = pm.process_handle if pm else None
        self.update_queue = None
        self.should_stop = threading.Event()
        self.is_active = False
        self.initialized = False
        self.version_config = version_config or {}
        self.series = self.version_config.get('series', '1.21.12')
        self.hitbox_pattern = self.version_config.get('hitbox_pattern', b'\xF3\x0F\x10\x79\x18\x49')
        self.shadow_pattern = self.version_config.get('shadow_pattern', b'\xF3\x44\x0F\x11\x42\x10')
        self.hitbox_patch_length = 5
        self.shadow_patch_length = 6
        self.shadow_value_on = self.version_config.get('shadow_value_on', 0.6)
        self.hitbox_addr = None
        self.shadow_addr = None
        self.hitbox_newmem = None
        self.shadow_newmem = None
        self.hitbox_original_bytes = None
        self.shadow_original_bytes = None
        self.shadow_patched = False
        self.current_hitbox = 1.0
        self.original_hitbox = 0.6
        self.PAGE_EXECUTE_READWRITE = 0x40
        self.MEM_COMMIT = 0x1000
        self.MEM_RESERVE = 0x2000
        self.MEM_RELEASE = 0x8000
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

    def set_version_config(self, version_config: dict):
        if version_config:
            self.version_config = version_config
            self.series = version_config.get('series', '1.21.12')
            self.hitbox_pattern = version_config.get('hitbox_pattern', self.hitbox_pattern)
            self.shadow_pattern = version_config.get('shadow_pattern', self.shadow_pattern)
            self.shadow_value_on = version_config.get('shadow_value_on', 0.6)

    def set_update_queue(self, update_queue: queue.Queue):
        self.update_queue = update_queue

    def set_pymem_process(self, pm: pymem.Pymem):
        self.pm = pm
        self.process_handle = pm.process_handle

    def update_status(self, message, color):
        if self.update_queue:
            self.update_queue.put(('status_update', ('hitbox', message, color)))

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
        if not self.hitbox_addr or not self.shadow_addr or not self.initialized:
            return False
        if not self.validate_process():
            self.initialized = False
            self.hitbox_addr = None
            self.shadow_addr = None
            return False
        try:
            self.pm.read_bytes(self.hitbox_addr, 5)
            self.pm.read_bytes(self.shadow_addr, 6)
            return True
        except Exception:
            self.initialized = False
            self.hitbox_addr = None
            self.shadow_addr = None
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

    def find_hitbox_addresses(self, retries=3, delay=1.0):
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
                hitbox_matches = [m.start() for m in re.finditer(re.escape(self.hitbox_pattern), bytes_read)]
                shadow_matches = [m.start() for m in re.finditer(re.escape(self.shadow_pattern), bytes_read)]
                if not hitbox_matches or not shadow_matches:
                    time.sleep(delay)
                    continue
                self.hitbox_addr = base_address + hitbox_matches[0]
                self.shadow_addr = base_address + shadow_matches[0]
                self.hitbox_original_bytes = self.pm.read_bytes(self.hitbox_addr, self.hitbox_patch_length)
                self.shadow_original_bytes = self.pm.read_bytes(self.shadow_addr, self.shadow_patch_length)
                self.hitbox_newmem = self.allocate_near(self.hitbox_addr, 0x100)
                self.shadow_newmem = self.allocate_near(self.shadow_addr, 0x100)
                if not self.hitbox_newmem or not self.shadow_newmem:
                    time.sleep(delay)
                    continue
                self.initialized = True
                self.shadow_patched = False
                self.update_status("Initialized & Ready", '#00e676')
                print(f"Hitbox: Initialized at 0x{self.hitbox_addr:X}, shadow address 0x{self.shadow_addr:X}")
                return True
            except Exception:
                time.sleep(delay)
        self.update_status("Pattern/Memory Init Failed", '#ff5252')
        return False

    def _write_shadow_patch(self):
        if not self.shadow_addr or not self.shadow_newmem:
            return False
        try:
            shellcode = b'\xC7\x42\x10' + struct.pack('<f', self.shadow_value_on)
            return_address = self.shadow_addr + 6
            jmp_back = return_address - (self.shadow_newmem + len(shellcode) + 5)
            if not -0x80000000 <= jmp_back <= 0x7FFFFFFF:
                return False
            shellcode += b'\xE9' + struct.pack('<i', jmp_back)
            try:
                self.pm.write_bytes(self.shadow_newmem, shellcode, len(shellcode))
            except:
                bytes_written = ctypes.c_size_t()
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.shadow_newmem), shellcode, len(shellcode), ctypes.byref(bytes_written))
            jmp_offset = self.shadow_newmem - (self.shadow_addr + 5)
            patch_bytes = b'\xE9' + struct.pack('<i', jmp_offset) + b'\x90'
            old_protect = wintypes.DWORD()
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.shadow_addr), 6,
                                  self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect))
            try:
                self.pm.write_bytes(self.shadow_addr, patch_bytes, len(patch_bytes))
            except:
                bytes_written = ctypes.c_size_t()
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.shadow_addr), patch_bytes, len(patch_bytes), ctypes.byref(bytes_written))
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.shadow_addr), 6, old_protect.value, ctypes.byref(old_protect))
            self.shadow_patched = True
            return True
        except Exception:
            return False

    def _write_hitbox_to_memory(self, value: float):
        if not self.hitbox_addr or not self.hitbox_newmem:
            return False
        try:
            if self.series == "1.21.12":
                shellcode = b'\xC7\x41\x18' + struct.pack('<f', value)
            else:
                shellcode = b'\xC7\x40\x18' + struct.pack('<f', value)
            return_address = self.hitbox_addr + 5
            jmp_back = return_address - (self.hitbox_newmem + len(shellcode) + 5)
            if not -0x80000000 <= jmp_back <= 0x7FFFFFFF:
                return False
            shellcode += b'\xE9' + struct.pack('<i', jmp_back)
            try:
                self.pm.write_bytes(self.hitbox_newmem, shellcode, len(shellcode))
            except:
                bytes_written = ctypes.c_size_t()
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.hitbox_newmem), shellcode, len(shellcode), ctypes.byref(bytes_written))
            jmp_offset = self.hitbox_newmem - (self.hitbox_addr + 5)
            patch_bytes = b'\xE9' + struct.pack('<i', jmp_offset)

            old_protect = wintypes.DWORD()
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.hitbox_addr), 5,
                                  self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect))
            try:
                self.pm.write_bytes(self.hitbox_addr, patch_bytes, len(patch_bytes))
            except:
                bytes_written = ctypes.c_size_t()
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.hitbox_addr), patch_bytes, len(patch_bytes), ctypes.byref(bytes_written))
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.hitbox_addr), 5, old_protect.value, ctypes.byref(old_protect))

            multiplier = self.current_hitbox
            self.update_status(f"Active ({multiplier:.2f}x = {value:.2f})", '#00e676')
            return True
        except Exception as e:
            self.update_status(f"Write Error: {e.__class__.__name__}", '#ff5252')
            return False

    def set_hitbox_value(self, value):
        self.current_hitbox = float(value)
        if self.is_active and self.initialized:
            actual_value = self.original_hitbox * self.current_hitbox
            return self._write_hitbox_to_memory(actual_value)
        return True

    def enable_hitbox(self):
        if not self.initialized or not self.validate_address():
            if not self.find_hitbox_addresses():
                return False
        if self.is_active:
            return True
        try:
            if not self.shadow_patched:
                if not self._write_shadow_patch():
                    self.update_status("Shadow Patch Failed", '#ff5252')
                    return False
                self.shadow_patched = True
            actual_value = self.original_hitbox * self.current_hitbox
            if not self._write_hitbox_to_memory(actual_value):
                return False
            self.is_active = True
            return True
        except Exception as e:
            self.update_status(f"Enable Error: {e.__class__.__name__}", '#ff5252')
            return False

    def disable_hitbox(self):
        if not self.initialized or not self.is_active:
            return True
        try:
            if self.series == "1.21.13":
                self._write_hitbox_to_memory(0.6)
                time.sleep(0.05)
                self._restore_hitbox_original()
                self._restore_shadow_original()
            else:
                self._restore_hitbox_original()
                self._restore_shadow_original()
            self.is_active = False
            self.update_status("Inactive", '#b0b0b0')
            return True
        except Exception as e:
            self.update_status(f"Disable Error: {e.__class__.__name__}", '#ff5252')
            return False

    def _restore_hitbox_original(self):
        if not self.hitbox_addr or not self.hitbox_original_bytes:
            return True
        try:
            old_protect = wintypes.DWORD()
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.hitbox_addr), 5,
                                  self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect))
            try:
                self.pm.write_bytes(self.hitbox_addr, self.hitbox_original_bytes, len(self.hitbox_original_bytes))
            except:
                bytes_written = ctypes.c_size_t()
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.hitbox_addr), self.hitbox_original_bytes,
                                        len(self.hitbox_original_bytes), ctypes.byref(bytes_written))
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.hitbox_addr), 5,
                                  old_protect.value, ctypes.byref(old_protect))
            return True
        except:
            return False

    def _restore_shadow_original(self):
        if not self.shadow_addr or not self.shadow_original_bytes or not self.shadow_patched:
            return True
        try:
            old_protect = wintypes.DWORD()
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.shadow_addr), 6,
                                  self.PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect))
            try:
                self.pm.write_bytes(self.shadow_addr, self.shadow_original_bytes, len(self.shadow_original_bytes))
            except:
                bytes_written = ctypes.c_size_t()
                self.WriteProcessMemory(self.process_handle, ctypes.c_void_p(self.shadow_addr), self.shadow_original_bytes,
                                        len(self.shadow_original_bytes), ctypes.byref(bytes_written))
            self.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.shadow_addr), 6,
                                  old_protect.value, ctypes.byref(old_protect))
            self.shadow_patched = False
            return True
        except:
            return False

    def reset_to_default(self, is_app_closing=False):
        if not self.validate_process():
            self.is_active = False
            self.initialized = False
            self.hitbox_addr = None
            self.shadow_addr = None
            self.shadow_patched = False
            self.update_status("Process closed. Reset.", '#b0b0b0')
            return True
        try:
            if self.is_active:
                self.disable_hitbox()
            if self.hitbox_addr and self.hitbox_original_bytes:
                self._restore_hitbox_original()
            if self.shadow_patched and self.shadow_addr and self.shadow_original_bytes:
                self._restore_shadow_original()

            if self.hitbox_newmem:
                self.VirtualFreeEx(self.process_handle, ctypes.c_void_p(self.hitbox_newmem), 0, self.MEM_RELEASE)
                self.hitbox_newmem = None
            if self.shadow_newmem:
                self.VirtualFreeEx(self.process_handle, ctypes.c_void_p(self.shadow_newmem), 0, self.MEM_RELEASE)
                self.shadow_newmem = None
            self.hitbox_addr = None
            self.shadow_addr = None
            self.initialized = False
            self.shadow_patched = False
            self.current_hitbox = 1.0
            self.update_status("Inactive", '#b0b0b0')
            return True
        except Exception as e:
            self.update_status(f"Reset Error: {e.__class__.__name__}", '#ff5252')
            return False

    def toggle(self):
        if not self.is_active:
            return self.enable_hitbox()
        else:
            return self.disable_hitbox()

    def start(self):
        return self.enable_hitbox()

    def stop(self, is_app_closing=False):
        self.should_stop.set()
        if is_app_closing:
            self.reset_to_default(is_app_closing=True)
        else:
            self.disable_hitbox()
        return True

    def initialize(self):
        return self.find_hitbox_addresses()