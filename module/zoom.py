import time
import keyboard
import struct
import re
import threading
import ctypes
from pynput import mouse
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


class ZoomController:
    def __init__(self):
        self.pm = None
        self.config_manager = ConfigManager("config.json")
        
        self.target_address = None
        self.default_value = None
        self.last_read_value = None
        self.min_zoom = 30.0
        self.max_zoom = 110.0
        self.zoom_change = self.min_zoom
        self.zoom_step = 1.0
        
        self.smooth_transition = True
        self.transition_speed = 0.001
        self.transition_steps = 50
        self.animation_type = 'ease_in_out_quad'
        
        self.enable_momentum = False
        self.scroll_momentum = 0.0
        self.momentum_decay = 0.5
        self.momentum_threshold = 0.01
        
        self.is_active = False
        self.initialized = False
        self.zoom_initialized = False
        self.zoom_ready_for_scroll = False
        self.scroll_animation_active = False
        self.animation_in_progress = False
        self.memory_operation_active = False
        
        self.should_stop = threading.Event()
        self.update_queue = None
        self.memory_lock = threading.Lock()
        self.listener_lock = threading.Lock()
        self.mouse_listener = None
        self.zoom_controller_thread = None
        self.monitoring_thread = None
        self.momentum_thread = None
        self.keybind_monitor_thread = None
        
        self.monitoring_active = False
        self.momentum_active = False
        self.keybind_monitoring_active = False
        
        self.hotbar_patch_address = None
        self.hotbar_original_bytes = None
        self.hotbar_patch_bytes = b'\x90\x90\x90'
        self.hotbar_pattern = b'\x89\x51\x10\x44\x88\x81\xB0\x00\x00\x00'
        self.hotbar_patched = False
        
        self.pattern = "?? ?? ?? ?? 00 00 70 42 6F 12"
        
        self.current_key = self.config_manager.get_keybind("zoom") or "c"
        
        self.last_scroll_time = 0
        self.rapid_scroll_mode = False

    def set_update_queue(self, update_queue):
        self.update_queue = update_queue
        if self.update_queue:
            self.update_queue.put(('status_update', ('zoom', "Zoom initialized", '#00e676')))

    def set_pymem_process(self, pm):
        self.set_pm(pm)

    def set_pm(self, pm):
        self.pm = pm
        if pm:
            if not self.initialized:
                self.initialize()
            elif self.config_manager.get_state("zoom") and not self.is_active:
                self.start()
        if pm and not self.keybind_monitoring_active:
            self.start_keybind_monitoring()

    def validate_process(self):
        try:
            if not self.pm or not self.pm.process_handle:
                return False
            ctypes.windll.kernel32.GetExitCodeProcess(self.pm.process_handle, ctypes.byref(ctypes.c_ulong()))
            return True
        except Exception:
            return False

    def validate_address(self):
        if not self.target_address or not self.initialized:
            return False
        if not self.validate_process():
            self.initialized = False
            self.target_address = None
            self.hotbar_patch_address = None
            self.hotbar_original_bytes = None
            self.hotbar_patched = False
            return False
        try:
            with self.memory_lock:
                self.pm.read_float(self.target_address)
            return True
        except Exception:
            self.initialized = False
            self.target_address = None
            self.hotbar_patch_address = None
            self.hotbar_original_bytes = None
            self.hotbar_patched = False
            return False
    
    def validate_hotbar_patch_address(self):
        if not self.hotbar_patch_address:
            return False
        try:
            test_bytes = self.pm.read_bytes(self.hotbar_patch_address, 3)
            return test_bytes == self.hotbar_original_bytes or test_bytes == self.hotbar_patch_bytes
        except Exception:
            return False

    def find_hotbar_patch_address(self, force_rescan=False):
        if self.hotbar_patch_address and not force_rescan:
            try:
                test_bytes = self.pm.read_bytes(self.hotbar_patch_address, 3)
                if test_bytes == self.hotbar_original_bytes or test_bytes == self.hotbar_patch_bytes:
                    return self.hotbar_patch_address
            except Exception:
                pass
        
        self.hotbar_patch_address = None
        self.hotbar_original_bytes = None
        self.hotbar_patched = False

        if not self.validate_process():
            return None

        try:
            mbi = MEMORY_BASIC_INFORMATION()
            address = 0
            
            while ctypes.windll.kernel32.VirtualQueryEx(
                self.pm.process_handle,
                ctypes.c_void_p(address),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi)
            ):
                if mbi.Protect == 32:
                    try:
                        memory = self.pm.read_bytes(mbi.BaseAddress, mbi.RegionSize)
                        index = memory.find(self.hotbar_pattern)
                        if index != -1:
                            match_address = mbi.BaseAddress + index
                            self.hotbar_patch_address = match_address
                            self.hotbar_original_bytes = memory[index:index+3]
                            if self.update_queue:
                                self.update_queue.put(('status_update', ('zoom', f"Hotbar patch address found at 0x{match_address:X}", '#00e676')))
                            return match_address
                    except Exception:
                        pass
                address += mbi.RegionSize
                if address >= 0x7FFFFFFFFFFFFFFF:
                    break
                    
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', "Failed to find hotbar patch address", '#ff5252')))
            return None
        except Exception as e:
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', f"Error finding hotbar patch: {e}", '#ff5252')))
            return None

    def apply_hotbar_patch(self):
        if self.hotbar_patched or not self.hotbar_patch_address:
            return False
            
        try:
            old_protect = ctypes.c_ulong()
            if not ctypes.windll.kernel32.VirtualProtectEx(
                self.pm.process_handle,
                ctypes.c_void_p(self.hotbar_patch_address),
                3,
                0x40,
                ctypes.byref(old_protect)
            ):
                return False
            
            self.pm.write_bytes(self.hotbar_patch_address, self.hotbar_patch_bytes, 3)
            
            ctypes.windll.kernel32.VirtualProtectEx(
                self.pm.process_handle,
                ctypes.c_void_p(self.hotbar_patch_address),
                3,
                old_protect.value,
                ctypes.byref(old_protect)
            )
            
            self.hotbar_patched = True
            return True
        except Exception as e:
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', f"Error applying hotbar patch: {e}", '#ff5252')))
            return False

    def remove_hotbar_patch(self):
        if not self.hotbar_patched or not self.hotbar_patch_address or not self.hotbar_original_bytes:
            return False
            
        try:
            old_protect = ctypes.c_ulong()
            if not ctypes.windll.kernel32.VirtualProtectEx(
                self.pm.process_handle,
                ctypes.c_void_p(self.hotbar_patch_address),
                3,
                0x40,
                ctypes.byref(old_protect)
            ):
                return False
            
            self.pm.write_bytes(self.hotbar_patch_address, self.hotbar_original_bytes, 3)
            
            ctypes.windll.kernel32.VirtualProtectEx(
                self.pm.process_handle,
                ctypes.c_void_p(self.hotbar_patch_address),
                3,
                old_protect.value,
                ctypes.byref(old_protect)
            )
            
            self.hotbar_patched = False
            return True
        except Exception as e:
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', f"Error removing hotbar patch: {e}", '#ff5252')))
            return False

    def compile_wildcard_pattern(self, pattern):
        parts = pattern.split()
        regex_parts = []
        for part in parts:
            if part == '??':
                regex_parts.append(b'.')
            else:
                regex_parts.append(bytes.fromhex(part))
        return b''.join(regex_parts)

    def scan_memory(self, pattern, min_float=30.0, max_float=110.0, retries=3, delay=1.0):
        if self.initialized and self.validate_address():
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', f"Reusing cached address at 0x{self.target_address:X}", '#00e676')))
            return self.target_address, self.default_value
        if not self.validate_process():
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', "Invalid process handle", '#ff5252')))
            return None, None
        self.target_address = None
        self.initialized = False
        for attempt in range(retries):
            try:
                mbi = MEMORY_BASIC_INFORMATION()
                address = 0
                regex_pattern = self.compile_wildcard_pattern(pattern)
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
                                    if min_float <= float_value <= max_float:
                                        with self.memory_lock:
                                            original_test_value = self.pm.read_float(match_address)
                                            test_value = 55.5
                                            self.pm.write_float(match_address, test_value)
                                            time.sleep(0.01)
                                            read_test_value = self.pm.read_float(match_address)
                                            self.pm.write_float(match_address, original_test_value)
                                        if abs(read_test_value - test_value) < 0.01:
                                            self.initialized = True
                                            self.target_address = match_address
                                            self.default_value = float_value
                                            if self.update_queue:
                                                self.update_queue.put(('status_update', ('zoom', f"Zoom address found at 0x{match_address:X}", '#00e676')))
                                            return match_address, float_value
                        except Exception:
                            pass
                    address += mbi.RegionSize
                    if address >= 0x7FFFFFFFFFFFFFFF:
                        break
                if self.update_queue:
                    self.update_queue.put(('status_update', ('zoom', f"Zoom address not found (attempt {attempt + 1}/{retries})", '#ff5252')))
                time.sleep(delay)
            except Exception as e:
                if self.update_queue:
                    self.update_queue.put(('status_update', ('zoom', f"Error scanning memory: {e}", '#ff5252')))
                time.sleep(delay)
        if self.update_queue:
            self.update_queue.put(('status_update', ('zoom', "Failed to initialize Zoom", '#ff5252')))
        return None, None

    def initialize(self):
        if self.initialized and self.validate_address():
            if not self.hotbar_patch_address or not self.validate_hotbar_patch_address():
                if not self.find_hotbar_patch_address(force_rescan=True):
                    if self.update_queue:
                        self.update_queue.put(('status_update', ('zoom', "Warning: Hotbar lock unavailable", '#ffa726')))
            return True
        if not self.validate_process():
            return False
        try:
            self.target_address, self.default_value = self.scan_memory(self.pattern)
            if self.target_address is None:
                if self.update_queue:
                    self.update_queue.put(('status_update', ('zoom', "Failed to find zoom address", '#ff5252')))
                return False
            self.last_read_value = self.default_value
            if 30.0 <= self.default_value <= 110.0:
                with self.memory_lock:
                    self.pm.write_float(self.target_address, 110.0)
                self.default_value = 110.0
                self.last_read_value = 110.0
            else:
                if self.update_queue:
                    self.update_queue.put(('status_update', ('zoom', "Invalid default zoom value", '#ff5252')))
                return False
            if not self.find_hotbar_patch_address():
                if self.update_queue:
                    self.update_queue.put(('status_update', ('zoom', "Warning: Hotbar lock unavailable", '#ffa726')))
            self.initialized = True
            print(f"Zoom: Initialized at 0x{self.target_address:X}, default value: {self.default_value}, hotbar address: 0x{self.hotbar_patch_address:X}")
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', "Zoom initialized successfully", '#00e676')))
            return True
        except Exception as e:
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', f"Error initializing zoom: {e}", '#ff5252')))
            return False

    def reset_to_default(self, is_app_closing=False):
        if self.target_address and self.initialized and self.validate_address():
            try:
                with self.memory_lock:
                    current_value = self.pm.read_float(self.target_address)
                    if abs(current_value - self.default_value) > 0.01:
                        self.pm.write_float(self.target_address, self.default_value)
                        if self.update_queue:
                            self.update_queue.put(('status_update', ('zoom', f"Reset to default value {self.default_value}", '#b0b0b0')))
            except Exception as e:
                if self.update_queue:
                    self.update_queue.put(('status_update', ('zoom', f"Error resetting zoom: {e}", '#ff5252')))
        self.zoom_change = self.min_zoom
        self.zoom_initialized = False
        self.zoom_ready_for_scroll = False
        self.scroll_animation_active = False
        self.animation_in_progress = False

    def monitor_default_value(self):
        while self.monitoring_active and not self.should_stop.is_set():
            if not self.validate_address():
                if not self.initialize():
                    self.stop(save_config=False)
                    return
            try:
                if not self.memory_operation_active and not self.zoom_initialized:
                    with self.memory_lock:
                        current_value = self.pm.read_float(self.target_address)
                    if abs(current_value - self.last_read_value) > 0.1:
                        self.default_value = current_value
                        self.last_read_value = current_value
                    else:
                        self.last_read_value = current_value
                time.sleep(0.01)
            except Exception as e:
                if self.update_queue:
                    self.update_queue.put(('status_update', ('zoom', f"Error monitoring zoom: {e}", '#ff5252')))
                time.sleep(1)

    def start_monitoring(self):
        if not self.monitoring_active:
            self.monitoring_active = True
            self.should_stop.clear()
            self.monitoring_thread = threading.Thread(target=self.monitor_default_value, daemon=True)
            self.monitoring_thread.start()
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', "Zoom monitoring started", '#00e676')))

    def stop_monitoring(self):
        if self.monitoring_active:
            self.monitoring_active = False
            if self.monitoring_thread and threading.current_thread() is not self.monitoring_thread:
                try:
                    self.monitoring_thread.join(timeout=1)
                except Exception:
                    pass
                self.monitoring_thread = None
            else:
                self.monitoring_thread = None
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', "Zoom monitoring stopped", '#b0b0b0')))

    def monitor_keybind(self):
        while self.keybind_monitoring_active and not self.should_stop.is_set():
            try:
                new_key = self.config_manager.get_keybind("zoom") or "c"
                if new_key != self.current_key:
                    self.current_key = new_key
                    if self.update_queue:
                        self.update_queue.put(('status_update', ('zoom', f"Keybind changed to '{self.current_key.upper()}'", '#00e676')))
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

    def ease_in_out_quad(self, t):
        t *= 2
        if t < 1:
            return 0.5 * t * t
        t -= 1
        return -0.5 * (t * (t - 2) - 1)

    def ease_out_bounce(self, t):
        if t < 1 / 2.75:
            return 7.5625 * t * t
        elif t < 2 / 2.75:
            t -= 1.5 / 2.75
            return 7.5625 * t * t + 0.75
        elif t < 2.5 / 2.75:
            t -= 2.25 / 2.75
            return 7.5625 * t * t + 0.9375
        else:
            t -= 2.625 / 2.75
            return 7.5625 * t * t + 0.984375

    def get_easing_value(self, t, animation_type):
        if animation_type == "ease_in_out_quad":
            return self.ease_in_out_quad(t)
        elif animation_type == "ease_out_bounce":
            return self.ease_out_bounce(t)
        else:
            return t

    def perform_memory_operation(self, target_address, start_value, end_value, duration=0.05, steps=50):
        self.zoom_ready_for_scroll = False
        self.animation_in_progress = True
        if not self.validate_address():
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', "Invalid zoom address", '#ff5252')))
            self.animation_in_progress = False
            return
        duration = min(0.2, max(0.05, abs(end_value - start_value) * 0.002))
        delay = duration / steps
        for i in range(steps + 1):
            if not self.is_active or not keyboard.is_pressed(self.current_key) or self.should_stop.is_set():
                try:
                    if self.validate_address():
                        with self.memory_lock:
                            self.pm.write_float(target_address, self.default_value)
                except Exception:
                    pass
                self.animation_in_progress = False
                return
            t = i / steps
            eased_t = self.get_easing_value(t, self.animation_type)
            current_value = start_value + (end_value - start_value) * eased_t
            try:
                with self.memory_lock:
                    self.pm.write_float(target_address, current_value)
            except Exception as e:
                if self.update_queue:
                    self.update_queue.put(('status_update', ('zoom', f"Error in zoom operation: {e}", '#ff5252')))
                break
            time.sleep(delay)
        self.animation_in_progress = False
        self.zoom_ready_for_scroll = True
        self.zoom_change = end_value

    def momentum_scroll_handler(self):
        while self.momentum_active and not self.should_stop.is_set():
            if self.enable_momentum and abs(self.scroll_momentum) > self.momentum_threshold and keyboard.is_pressed(self.current_key) and not self.scroll_animation_active:
                new_zoom = self.zoom_change + (self.scroll_momentum * self.zoom_step * 0.5)
                new_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))
                if new_zoom != self.zoom_change:
                    self.scroll_animation_active = True
                    self.perform_memory_operation(
                        self.target_address,
                        self.zoom_change,
                        new_zoom,
                        duration=0.005,
                        steps=5
                    )
                    self.zoom_change = new_zoom
                    self.scroll_animation_active = False
                self.scroll_momentum *= self.momentum_decay
            else:
                self.scroll_momentum = 0.0
            time.sleep(0.005)

    def start_momentum_handler(self):
        if not self.momentum_active:
            self.momentum_active = True
            self.should_stop.clear()
            self.momentum_thread = threading.Thread(target=self.momentum_scroll_handler, daemon=True)
            self.momentum_thread.start()

    def stop_momentum_handler(self):
        if self.momentum_active:
            self.momentum_active = False
            if self.momentum_thread and threading.current_thread() is not self.momentum_thread:
                try:
                    self.momentum_thread.join(timeout=1)
                except Exception:
                    pass
                self.momentum_thread = None
            else:
                self.momentum_thread = None

    def on_scroll(self, x, y, dx, dy):
        if not self.is_active or not keyboard.is_pressed(self.current_key) or self.should_stop.is_set():
            return True
        if (not self.zoom_ready_for_scroll or 
            self.scroll_animation_active or 
            self.animation_in_progress):
            if self.mouse_listener:
                self.mouse_listener.suppress_event()
            return False
        if not self.validate_address():
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', "Invalid zoom address during scroll", '#ff5252')))
            return True
        current_time = time.time()
        if current_time - self.last_scroll_time < 0.05:
            scroll_multiplier = 5.0
            self.rapid_scroll_mode = True
        elif current_time - self.last_scroll_time < 0.1:
            scroll_multiplier = 3.0
            self.rapid_scroll_mode = True
        else:
            scroll_multiplier = 1.0
            self.rapid_scroll_mode = False
        self.last_scroll_time = current_time
        if self.enable_momentum:
            self.scroll_momentum += dy * 1.0 * scroll_multiplier
        previous_zoom = self.zoom_change
        zoom_change_amount = self.zoom_step * scroll_multiplier
        if dy > 0:
            new_zoom = min(self.max_zoom, self.zoom_change + zoom_change_amount)
        elif dy < 0:
            new_zoom = max(self.min_zoom, self.zoom_change - zoom_change_amount)
        else:
            new_zoom = self.zoom_change
        if new_zoom != previous_zoom:
            self.zoom_change = new_zoom
            if self.memory_operation_active and self.validate_address():
                try:
                    with self.memory_lock:
                        self.pm.write_float(self.target_address, new_zoom)
                except Exception as e:
                    if self.update_queue:
                        self.update_queue.put(('status_update', ('zoom', f"Error writing zoom value: {e}", '#ff5252')))
        if self.mouse_listener:
            self.mouse_listener.suppress_event()
        return False

    def start_scroll_blocking(self):
        with self.listener_lock:
            if self.mouse_listener:
                try:
                    self.mouse_listener.stop()
                except:
                    pass
                self.mouse_listener = None
            
            self.mouse_listener = mouse.Listener(on_scroll=self.on_scroll)
            self.mouse_listener.start()
            self.start_momentum_handler()
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', "Zoom scroll handling started", '#00e676')))

    def stop_scroll_blocking(self):
        with self.listener_lock:
            if self.mouse_listener:
                self.stop_momentum_handler()
                try:
                    self.mouse_listener.stop()
                except AttributeError:
                    pass
                self.mouse_listener = None
                if self.update_queue:
                    self.update_queue.put(('status_update', ('zoom', "Zoom scroll handling stopped", '#b0b0b0')))

    def run_zoom_controller(self):
        last_zoom_change = self.zoom_change
        while self.is_active and not self.should_stop.is_set():
            if not self.validate_address():
                if not self.initialize():
                    self.stop(save_config=False)
                    return
            try:
                if keyboard.is_pressed(self.current_key):
                    if not self.memory_operation_active:
                        if self.hotbar_patch_address and not self.hotbar_patched:
                            self.apply_hotbar_patch()
                        
                        self.memory_operation_active = True
                        self.zoom_change = self.min_zoom
                        self.perform_memory_operation(
                            self.target_address, self.pm.read_float(self.target_address), self.zoom_change
                        )
                        self.zoom_initialized = True
                        if self.update_queue:
                            self.update_queue.put(('status_update', ('zoom', "Zooming", '#00e676')))
                    elif abs(self.zoom_change - last_zoom_change) > 0.001:
                        with self.memory_lock:
                            current_fov = self.pm.read_float(self.target_address)
                        if abs(current_fov - self.zoom_change) > 0.05:
                            try:
                                with self.memory_lock:
                                    self.pm.write_float(self.target_address, self.zoom_change)
                            except Exception as e:
                                if self.update_queue:
                                    self.update_queue.put(('status_update', ('zoom', f"Error writing zoom value: {e}", '#ff5252')))
                else:
                    if self.memory_operation_active:
                        if self.hotbar_patched:
                            self.remove_hotbar_patch()
                        
                        self.memory_operation_active = False
                        self.zoom_change = self.default_value
                        try:
                            if self.validate_address():
                                with self.memory_lock:
                                    self.pm.write_float(self.target_address, self.default_value)
                        except Exception as e:
                            if self.update_queue:
                                self.update_queue.put(('status_update', ('zoom', f"Error reverting zoom: {e}", '#ff5252')))
                        self.zoom_initialized = False
                        self.zoom_ready_for_scroll = False
                        self.scroll_animation_active = False
                        self.animation_in_progress = False
                        if self.update_queue:
                            self.update_queue.put(('status_update', ('zoom', "Not Zooming", '#b0b0b0')))
                last_zoom_change = self.zoom_change
                time.sleep(0.01)
            except Exception as e:
                if self.update_queue:
                    self.update_queue.put(('status_update', ('zoom', f"Error in zoom controller: {e}", '#ff5252')))
                self.stop(save_config=False)
                return
        self.reset_to_default()

    def toggle(self):
        if not self.is_active:
            self.start()
        else:
            self.stop()

    def start(self, key=None):
        if not self.is_active:
            if not self.initialized:
                if not self.initialize():
                    if self.update_queue:
                        self.update_queue.put(('status_update', ('zoom', "Failed to start Zoom", '#ff5252')))
                    return False
            self.is_active = True
            self.config_manager.set_state("zoom", True)
            self.should_stop.clear()
            
            self.start_monitoring()
            self.start_scroll_blocking()
            
            self.zoom_controller_thread = threading.Thread(target=self.run_zoom_controller, daemon=True)
            self.zoom_controller_thread.start()
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', "Zoom enabled", '#00e676')))
            return True
        return True

    def stop(self, save_config=True, is_app_closing=False):
        if self.is_active:
            self.is_active = False
            
            if save_config and not is_app_closing:
                self.config_manager.set_state("zoom", False)
            
            self.should_stop.set()
            
            if self.hotbar_patched:
                self.remove_hotbar_patch()
            
            self.stop_monitoring()
            self.stop_scroll_blocking()
            
            if save_config or is_app_closing:
                self.stop_keybind_monitoring()
            
            self.reset_to_default()
            if self.zoom_controller_thread and threading.current_thread() is not self.zoom_controller_thread:
                try:
                    self.zoom_controller_thread.join(timeout=2)
                except Exception:
                    pass
                self.zoom_controller_thread = None
            else:
                self.zoom_controller_thread = None
            self.reset_to_default()
            if self.update_queue:
                self.update_queue.put(('status_update', ('zoom', "Zoom disabled", '#b0b0b0')))
        return True

    def cleanup(self):
        if self.hotbar_patched:
            self.remove_hotbar_patch()
        self.stop_keybind_monitoring()
        self.stop(is_app_closing=True)