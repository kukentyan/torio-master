import pymem
import pymem.pattern
import struct
import ctypes
from ctypes import wintypes
import threading
import time
import queue

class AntiKnockbackController:
    def __init__(self, pm: pymem.Pymem = None):
        self.pm = pm
        self.process_handle = pm.process_handle if pm else None
        self.update_queue = None
        self.should_stop = threading.Event()
        self.is_active = False
        self.initialized = False
        self.hook_address = None
        self.original_bytes = None
        self.allocated_memory = None
        self.kb_xz_mult = 0.8
        self.kb_y_mult = 0.8
        self.kb_x_mult_addr = None
        self.kb_y_mult_addr = None
        self.kb_z_mult_addr = None
        self.code_start = None
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.VirtualAllocEx = self.kernel32.VirtualAllocEx
        self.VirtualAllocEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
        self.VirtualAllocEx.restype = wintypes.LPVOID
        self.VirtualFreeEx = self.kernel32.VirtualFreeEx
        self.VirtualFreeEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]
        self.VirtualFreeEx.restype = wintypes.BOOL
        self.MEM_COMMIT = 0x1000
        self.MEM_RESERVE = 0x2000
        self.PAGE_EXECUTE_READWRITE = 0x40
        self.MEM_RELEASE = 0x8000

    def set_update_queue(self, update_queue: queue.Queue):
        self.update_queue = update_queue

    def set_pymem_process(self, pm: pymem.Pymem):
        self.pm = pm
        self.process_handle = pm.process_handle

    def update_status(self, message, color):
        if self.update_queue:
            self.update_queue.put(('status_update', ('antiknockback', message, color)))

    def validate_process(self):
        try:
            if not self.pm or not self.process_handle:
                return False
            exit_code = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetExitCodeProcess(self.process_handle, ctypes.byref(exit_code)) == 0:
                return False
            return exit_code.value == 259
        except:
            return False

    def validate_address(self):
        if not self.hook_address or not self.initialized:
            return False
        if not self.validate_process():
            self.initialized = False
            self.hook_address = None
            return False
        try:
            self.pm.read_bytes(self.hook_address, 5)
            return True
        except:
            self.initialized = False
            self.hook_address = None
            return False

    def allocate_near(self, base_addr, size=0x1000, max_distance=0x1F400000):
        step = 0x10000
        for offset in range(0, max_distance, step):
            for addr in (base_addr + offset, base_addr - offset):
                if addr <= 0:
                    continue
                alloc = self.VirtualAllocEx(
                    self.process_handle,
                    ctypes.c_void_p(addr),
                    size,
                    self.MEM_COMMIT | self.MEM_RESERVE,
                    self.PAGE_EXECUTE_READWRITE
                )
                if alloc:
                    return alloc
        raise Exception("Failed to allocate memory near base")

    def float_to_bytes(self, f):
        return struct.pack("<f", f)

    def find_pattern_and_setup_hook(self, retries=3, delay=1.0):
        if self.initialized and self.validate_address():
            return True
        if not self.validate_process():
            return False
        module_base = self.pm.process_base
        for attempt in range(retries):
            try:
                pattern = b"\xF2\x0F\x11\x40\x18\x44"
                self.hook_address = pymem.pattern.pattern_scan_module(self.process_handle, module_base, pattern)
                if not self.hook_address:
                    time.sleep(delay)
                    continue
                self.original_bytes = self.pm.read_bytes(self.hook_address, 5)
                self.allocated_memory = self.allocate_near(self.hook_address, size=0x1000)
                self.code_start = self.allocated_memory + 0x20
                offset = 0
                self.kb_x_mult_addr = self.allocated_memory + offset; offset += 4
                self.kb_z_mult_addr = self.allocated_memory + offset; offset += 4
                self.kb_y_mult_addr = self.allocated_memory + offset; offset += 4
                self.pm.write_bytes(self.kb_x_mult_addr, self.float_to_bytes(self.kb_xz_mult), 4)
                self.pm.write_bytes(self.kb_z_mult_addr, self.float_to_bytes(self.kb_xz_mult), 4)
                self.pm.write_bytes(self.kb_y_mult_addr, self.float_to_bytes(self.kb_y_mult), 4)
                self.initialized = True
                self.update_status("Initialized & Ready", '#00e676')
                print(f"AntiKnockback: Initialized at 0x{self.hook_address:X}")
                return True
            except Exception as e:
                time.sleep(delay)
        self.update_status("Pattern/Memory Init Failed", '#ff5252')
        return False

    def _write_config_values(self):
        if not self.initialized:
            return
        try:
            self.pm.write_bytes(self.kb_x_mult_addr, self.float_to_bytes(self.kb_xz_mult), 4)
            self.pm.write_bytes(self.kb_z_mult_addr, self.float_to_bytes(self.kb_xz_mult), 4)
            self.pm.write_bytes(self.kb_y_mult_addr, self.float_to_bytes(self.kb_y_mult), 4)
        except:
            pass

    def set_multipliers(self, xz_mult=None, y_mult=None):
        changed = False
        if xz_mult is not None:
            self.kb_xz_mult = float(xz_mult)
            changed = True
        if y_mult is not None:
            self.kb_y_mult = float(y_mult)
            changed = True
        if changed and self.initialized:
            self._write_config_values()
            self.update_status(f"X/Z:{self.kb_xz_mult:.2f} Y:{self.kb_y_mult:.2f}", '#00e676' if self.is_active else '#b0b0b0')

    def enable_antiknockback(self):
        if not self.initialized or not self.validate_address():
            if not self.find_pattern_and_setup_hook():
                return False
        if self.is_active:
            return True
        try:
            self._write_config_values()
            shellcode = b""
            # X
            shellcode += b"\xF3\x0F\x10\x02"  # movss xmm0,[rdx]
            shellcode += b"\xF3\x0F\x59\x05" + struct.pack("<i", self.kb_x_mult_addr - (self.code_start + len(shellcode) + 4))
            shellcode += b"\xF3\x0F\x11\x40\x18"  # movss [rax+18],xmm0
            # Z
            shellcode += b"\xF3\x0F\x10\x42\x04"  # movss xmm0,[rdx+04]
            shellcode += b"\xF3\x0F\x59\x05" + struct.pack("<i", self.kb_z_mult_addr - (self.code_start + len(shellcode) + 4))
            shellcode += b"\xF3\x0F\x11\x40\x1C"  # movss [rax+1C],xmm0
            # Y
            shellcode += b"\xF3\x0F\x10\x42\x08"  # movss xmm0,[rdx+08]
            shellcode += b"\xF3\x0F\x59\x05" + struct.pack("<i", self.kb_y_mult_addr - (self.code_start + len(shellcode) + 4))
            shellcode += b"\xF3\x0F\x11\x40\x20"  # movss [rax+20],xmm0
            jmp_back_offset = (self.hook_address + 5) - (self.code_start + len(shellcode) + 5)
            shellcode += b"\xE9" + struct.pack("<i", jmp_back_offset)
            old_protect = ctypes.c_ulong()
            ctypes.windll.kernel32.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.code_start), len(shellcode), 0x40, ctypes.byref(old_protect))
            self.pm.write_bytes(self.code_start, shellcode, len(shellcode))
            ctypes.windll.kernel32.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.code_start), len(shellcode), old_protect, ctypes.byref(ctypes.c_ulong()))
            rel_jmp = self.code_start - (self.hook_address + 5)
            patch = b"\xE9" + struct.pack("<i", rel_jmp)
            ctypes.windll.kernel32.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.hook_address), 5, 0x40, ctypes.byref(old_protect))
            self.pm.write_bytes(self.hook_address, patch, 5)
            ctypes.windll.kernel32.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.hook_address), 5, old_protect, ctypes.byref(ctypes.c_ulong()))
            self.is_active = True
            self.update_status(f"Active (X/Z:{self.kb_xz_mult:.2f} Y:{self.kb_y_mult:.2f})", '#00e676')
            return True
        except Exception as e:
            self.update_status(f"Enable Error: {e.__class__.__name__}", '#ff5252')
            return False

    def disable_antiknockback(self):
        if not self.is_active or not self.initialized:
            return True
        try:
            old_protect = ctypes.c_ulong()
            ctypes.windll.kernel32.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.hook_address), 5, 0x40, ctypes.byref(old_protect))
            self.pm.write_bytes(self.hook_address, self.original_bytes, 5)
            ctypes.windll.kernel32.VirtualProtectEx(self.process_handle, ctypes.c_void_p(self.hook_address), 5, old_protect, ctypes.byref(ctypes.c_ulong()))
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
            self.allocated_memory = None
            self.hook_address = None
            self.update_status("Process closed. Reset.", '#b0b0b0')
            return True
        try:
            if self.is_active:
                self.disable_antiknockback()

            if self.allocated_memory and (not self.validate_address() or is_app_closing):
                self.VirtualFreeEx(self.process_handle, self.allocated_memory, 0, self.MEM_RELEASE)
                self.allocated_memory = None
                self.code_start = None
                self.kb_x_mult_addr = None
                self.kb_y_mult_addr = None
                self.kb_z_mult_addr = None
                self.initialized = False
                self.hook_address = None
                self.original_bytes = None
            self.update_status("Inactive", '#b0b0b0')
            return True
        except Exception as e:
            self.update_status(f"Reset Error: {e.__class__.__name__}", '#ff5252')
            return False

    def toggle(self):
        if not self.is_active:
            self.enable_antiknockback()
        else:
            self.disable_antiknockback()

    def start(self):
        return self.enable_antiknockback()

    def stop(self, is_app_closing=False):
        self.should_stop.set()
        if is_app_closing:
            self.reset_to_default(is_app_closing=True)
        else:
            self.disable_antiknockback()
        return True

    def initialize(self):
        return self.find_pattern_and_setup_hook()