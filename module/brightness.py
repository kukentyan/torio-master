import pymem
from pymem import Pymem
import time
import threading
import keyboard
import ctypes
import struct
import re
from config import ConfigManager

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_ulong),
        ("PartitionKey", ctypes.c_ushort),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
    ]

class BrightnessController:
    def __init__(self):
        self.pm = None
        self.config_manager = ConfigManager("config.json")
        self.update_queue = None
        self.should_stop = threading.Event()
        self.addresses = []
        self.is_active = self.config_manager.get_state('brightness') or False
        self.is_on = False
        self.original_values = []
        self.brightness_thread = None
        self.keybind_monitor_thread = None
        self.pattern = "?? ?? ?? ?? 00 00 00 3F 6F 12 83 3A"
        self.initialized = False
        self.keybind_monitoring_active = False
        self.current_key = self.config_manager.get_keybind('brightness') or 'g'

    def set_update_queue(self, update_queue):
        self.update_queue = update_queue

    def set_pymem_process(self, pm):
        self.pm = pm
        if self.is_active:
            self.start()

    def validate_process(self):
        try:
            if not self.pm or not self.pm.process_handle:
                return False
            ctypes.windll.kernel32.GetExitCodeProcess(self.pm.process_handle, ctypes.byref(ctypes.c_ulong()))
            return True
        except Exception:
            return False

    def validate_addresses(self):
        if not self.addresses or not self.initialized:
            return False
        if not self.validate_process():
            self.initialized = False
            self.addresses = []
            self.original_values = []
            return False
        valid = True
        for addr in self.addresses:
            try:
                self.pm.read_float(addr)
            except Exception:
                valid = False
        if not valid:
            self.initialized = False
            self.addresses = []
            self.original_values = []
        return valid

    def compile_wildcard_pattern(self, pattern):
        parts = pattern.split()
        regex_parts = []
        for part in parts:
            if part == '??':
                regex_parts.append(b'.')
            else:
                regex_parts.append(bytes.fromhex(part))
        return b''.join(regex_parts)

    def scan_memory_with_wildcard(self, pattern):
        if not self.validate_process():
            return None
        try:
            mbi = MEMORY_BASIC_INFORMATION()
            address = 0
            regex_pattern = self.compile_wildcard_pattern(pattern)
            candidates = []
            
            while ctypes.windll.kernel32.VirtualQueryEx(
                self.pm.process_handle,
                ctypes.c_void_p(address),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi)
            ):
                if mbi.Protect == 4:
                    try:
                        memory = self.pm.read_bytes(mbi.BaseAddress, mbi.RegionSize)
                        for match in re.finditer(re.escape(regex_pattern).replace(b'\\.', b'.'), memory, re.DOTALL):
                            match_address = mbi.BaseAddress + match.start()
                            float_bytes = memory[match.start():match.start() + 4]
                            if len(float_bytes) == 4:
                                float_value = struct.unpack('<f', float_bytes)[0]
                                if 0.0 <= float_value <= 10.0:
                                    original_test_value = self.pm.read_float(match_address)
                                    test_value = 55.5
                                    self.pm.write_float(match_address, test_value)
                                    time.sleep(0.01)
                                    read_test_value = self.pm.read_float(match_address)
                                    self.pm.write_float(match_address, original_test_value)
                                    
                                    if abs(read_test_value - test_value) < 0.01:
                                        candidates.append(match_address)
                    except Exception:
                        pass
                address += mbi.RegionSize
                if address >= 0x7FFFFFFFFFFFFFFF:
                    break
            if candidates:
                return candidates
            else:
                return None
        except Exception:
            return None

    def initialize(self, retries=5, delay=2.0):
        if self.initialized and self.validate_addresses():
            return True
        self.addresses = []
        self.original_values = []
        self.initialized = False
        for attempt in range(retries):
            if not self.validate_process():
                time.sleep(delay)
                continue
            try:
                selected_addresses = self.scan_memory_with_wildcard(self.pattern)
                if selected_addresses:
                    self.addresses = selected_addresses
                    self.original_values = []
                    all_on = True
                    for addr in self.addresses:
                        current_value = self.pm.read_float(addr)
                        self.original_values.append(current_value)
                        if abs(current_value - 100.0) >= 0.01:
                            all_on = False
                    self.is_on = all_on
                    self.initialized = True
                    print(f"Brightness: Initialized at 0x{self.addresses[0]:X}")
                    if self.update_queue and self.is_active:
                        self.update_queue.put(('status_update', ('brightness', "Active", '#00e676')))
                    return True
            except Exception:
                time.sleep(delay)
        
        if self.update_queue:
            self.update_queue.put(('status_update', ('brightness', "Inactive", '#b0b0b0')))
        return False

    def reset_to_default(self, is_app_closing=False):
        if self.addresses and self.initialized and self.validate_addresses():
            try:
                for addr, orig_val in zip(self.addresses, self.original_values):
                    self.pm.write_float(addr, orig_val)
            except Exception:
                pass
        self.is_on = False

    def monitor_keybind(self):
        while self.keybind_monitoring_active and not self.should_stop.is_set():
            try:
                new_key = self.config_manager.get_keybind("brightness") or "g"
                if new_key != self.current_key:
                    self.current_key = new_key
                time.sleep(0.3)
            except Exception:
                time.sleep(1)

    def start_keybind_monitoring(self):
        if not self.keybind_monitoring_active:
            self.keybind_monitoring_active = True
            self.should_stop.clear()
            self.keybind_monitor_thread = threading.Thread(target=self.monitor_keybind, daemon=True)
            self.keybind_monitor_thread.start()

    def stop_keybind_monitoring(self):
        if self.keybind_monitoring_active:
            self.keybind_monitoring_active = False
            if self.keybind_monitor_thread and threading.current_thread() is not self.keybind_monitor_thread:
                try:
                    self.keybind_monitor_thread.join(timeout=1)
                except Exception:
                    pass
                self.keybind_monitor_thread = None
            else:
                self.keybind_monitor_thread = None

    def brightness_loop(self):
        rescan_delay = 5.0
        last_rescan_time = 0
        while self.is_active and not self.should_stop.is_set():
            current_time = time.time()
            if not self.validate_addresses():
                if current_time - last_rescan_time >= rescan_delay:
                    if not self.initialize():
                        time.sleep(rescan_delay)
                    last_rescan_time = current_time
                continue
            try:
                external_change = False
                for i, addr in enumerate(self.addresses):
                    current_value = self.pm.read_float(addr)
                    if self.is_on:
                        if abs(current_value - 100.0) > 0.01:
                            self.original_values[i] = current_value
                            self.pm.write_float(addr, 100.0)
                            external_change = True
                    else:
                        if abs(current_value - self.original_values[i]) > 0.01:
                            self.original_values[i] = current_value
                            external_change = True
                if keyboard.is_pressed(self.current_key):
                    if not self.is_on:
                        for i, addr in enumerate(self.addresses):
                            current_val = self.pm.read_float(addr)
                            if abs(current_val - 100.0) > 0.01:
                                self.original_values[i] = current_val
                            self.pm.write_float(addr, 100.0)
                        self.is_on = True
                        if self.update_queue:
                            self.update_queue.put(('status_update', ('brightness', "On", '#00e676')))
                    else:
                        for i, addr in enumerate(self.addresses):
                            self.pm.write_float(addr, self.original_values[i])
                        self.is_on = False
                        if self.update_queue:
                            self.update_queue.put(('status_update', ('brightness', "Off", '#b0b0b0')))
                    while keyboard.is_pressed(self.current_key):
                        time.sleep(0.1)
                time.sleep(0.05)
            except Exception:
                self.stop()
                break
        if self.update_queue:
            self.update_queue.put(('status_update', ('brightness', "Inactive", '#b0b0b0')))

    def toggle(self):
        if not self.is_active:
            self.start()
        else:
            self.stop()
        self.config_manager.set_state('brightness', self.is_active)

    def start(self):
        if self.update_queue:
            self.update_queue.put(('status_update', ('brightness', "Loading...", '#ffeb3b')))
        if not self.initialize():
            if self.update_queue:
                self.update_queue.put(('status_update', ('brightness', "Inactive", '#b0b0b0')))
            return False
        self.is_active = True
        self.config_manager.set_state('brightness', self.is_active)
        self.should_stop.clear()
        if not self.keybind_monitoring_active:
            self.start_keybind_monitoring()
        if self.brightness_thread is None or not self.brightness_thread.is_alive():
            self.brightness_thread = threading.Thread(target=self.brightness_loop, daemon=True)
            self.brightness_thread.start()
        if self.update_queue:
            self.update_queue.put(('status_update', ('brightness', "Active", '#00e676')))
        return True

    def stop(self, is_app_closing=False):
        if self.is_active:
            self.is_active = False
            if not is_app_closing:
                self.config_manager.set_state('brightness', self.is_active)
            self.should_stop.set()
            self.stop_keybind_monitoring()
            if self.brightness_thread and self.brightness_thread.is_alive():
                self.brightness_thread.join(timeout=1)
            self.brightness_thread = None
            self.reset_to_default()
        return True

    def cleanup(self):
        self.stop_keybind_monitoring()
        self.stop(is_app_closing=True)