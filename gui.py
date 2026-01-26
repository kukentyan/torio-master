import customtkinter as ctk
from PIL import Image
import os
import sys
import threading
import time
import queue
import pymem
import ctypes
import re
# Local imports
from config import ConfigManager
from module.antiknockback import AntiKnockbackController
from module.reach import ReachController
from module.hitbox import HitboxController
from module.zoom import ZoomController
from module.brightness import BrightnessController
from keybindgui import KeybindWindow
from module.streamprotect import StreamProtectController
from module.speed import SpeedController
from module.coordinates import CoordinatesController
from module.autoclicker import AutoClickerController
from module.sprint import SprintController
from version_detector import MinecraftVersionDetector
from module.nohurtcam import NoHurtCamController
from module.truesight import TrueSightController
from module.timechanger import TimeChangerController

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")
COLORS = {
    "background": "#0a0a0f",
    "surface": "#12121a",
    "card": "#1a1a24",
    "card_hover": "#1f1f2e",
    "accent": "#ff4081",
    "accent_light": "#ff6b9d",
    "accent_dark": "#e91e63",
    "text": "#ffffff",
    "text_secondary": "#a0a0b0",
    "success": "#00e676",
    "border": "#2a2a38",
    "sidebar_active": "#ff4081",
    "gradient_start": "#ff4081",
    "gradient_end": "#e91e63",
}

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class ModernButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        default_kwargs = {
            "corner_radius": 12,
            "border_width": 0,
            "fg_color": COLORS["accent"],
            "hover_color": COLORS["accent_light"],
            "text_color": COLORS["text"],
            "font": ("Segoe UI", 13, "bold"),
            "height": 42,
        }
        default_kwargs.update(kwargs)
        super().__init__(master, **default_kwargs)
class ModernFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        default_kwargs = {
            "corner_radius": 16,
            "border_width": 1,
            "border_color": COLORS["border"],
            "fg_color": COLORS["card"],
        }
        default_kwargs.update(kwargs)
        super().__init__(master, **default_kwargs)
class ModernLabel(ctk.CTkLabel):
    def __init__(self, master, **kwargs):
        default_kwargs = {
            "text_color": COLORS["text"],
            "font": ("Segoe UI", 13),
        }
        default_kwargs.update(kwargs)
        super().__init__(master, **default_kwargs)
class ModernSlider(ctk.CTkSlider):
    def __init__(self, master, **kwargs):
        default_kwargs = {
            "button_color": COLORS["accent"],
            "button_hover_color": COLORS["accent_light"],
            "progress_color": COLORS["accent"],
            "fg_color": COLORS["border"],
            "height": 16,
            "corner_radius": 8,
        }
        default_kwargs.update(kwargs)
        super().__init__(master, **default_kwargs)
class ModernSwitch(ctk.CTkSwitch):
    def __init__(self, master, **kwargs):
        default_kwargs = {
            "fg_color": COLORS["border"],
            "progress_color": COLORS["accent"],
            "button_color": "#ffffff",
            "button_hover_color": "#ffffff",
            "text_color": COLORS["text"],
            "font": ("Segoe UI", 13, "bold"),
            "width": 44,
            "height": 22,
            "switch_width": 44,
            "switch_height": 22,
            "border_width": 0,
            "corner_radius": 11,
        }
        default_kwargs.update(kwargs)
        super().__init__(master, **default_kwargs)
class ModernCheckBox(ctk.CTkCheckBox):
    def __init__(self, master, **kwargs):
        default_kwargs = {
            "fg_color": COLORS["accent"],
            "border_color": COLORS["border"],
            "hover_color": COLORS["accent_light"],
            "text_color": COLORS["text"],
            "font": ("Segoe UI", 12),
            "border_width": 2,
            "corner_radius": 8,
        }
        default_kwargs.update(kwargs)
        super().__init__(master, **default_kwargs)
        
class MinecraftModApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._is_closing = False
        self._version_check_timer = None
        self.update_queue = queue.Queue()
        version_check = MinecraftVersionDetector.check_compatibility()
        if not version_check['supported']:
            self.show_version_error(version_check)
            self.start_version_monitoring()
            return
        self.minecraft_version = version_check['series_version']
        self.version_config = version_check['config']
        self._initialize_main_app()
    def _initialize_main_app(self):
        try:
            self.iconbitmap(resource_path("icons/icon.ico"))
        except Exception as e:
            print(f"Failed to set window icon: {e}")
   
        self.title(f"Torio Client - Minecraft {self.minecraft_version}")
        self.geometry("600x480")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["background"])
   
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.config = ConfigManager("config.json")
        self.update_queue = queue.Queue()
        self.game_process = None
   
        self.antikb_controller = AntiKnockbackController()
        self.reach_controller = ReachController()
        self.hitbox_controller = HitboxController(version_config=self.version_config)
        self.zoom_controller = ZoomController()
        self.brightness_controller = BrightnessController()
        self.speed_controller = SpeedController(version_config=self.version_config)
        self.coordinates_controller = CoordinatesController()
        self.autoclicker_controller = AutoClickerController()
        self.sprint_controller = SprintController()
        self.autoclicker_controller.set_update_queue(self.update_queue)
        self.nohurtcam_controller = NoHurtCamController()
        self.truesight_controller = TrueSightController()
        self.timechanger_controller = TimeChangerController()
   
        self.streamprotect_controller = StreamProtectController()
        self.streamprotect_controller.set_update_queue(self.update_queue)
   
        self.tab_labels = {}
        self.current_tab = "Player"
        self.tab_frames = {}
        self.widgets = {
            "Visual": {},
            "Combat": {},
            "Movement": {},
            "Misc": {}
        }
   
        self.create_loading_screen()
        self.create_main_widgets()
   
        self.after(100, self.start_initialization_thread)
        self.after(100, self.process_queue)
   
        self.check_process_timer = self.after(5000, self.check_process_alive)
    def show_version_error(self, version_check):
        try:
            self.iconbitmap(resource_path("icons/icon.ico"))
        except:
            pass
   
        self.title("Torio Client - Version Error")
        self.geometry("520x420")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["background"])
   
        error_frame = ModernFrame(self, fg_color=COLORS["surface"])
        error_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9, relheight=0.85)
   
        ModernLabel(
            error_frame,
            text="⚠",
            font=("Segoe UI", 48),
            text_color='#ff5252'
        ).pack(pady=(30, 15))
   
        ModernLabel(
            error_frame,
            text="Unsupported Minecraft Version",
            font=("Segoe UI", 20, "bold"),
            text_color='#ff5252'
        ).pack(pady=12)
   
        if version_check['installed_version']:
            full_version = version_check['installed_version']
            match = re.match(r'(\d+\.\d+\.\d{3})', full_version)
            display_version = match.group(1) if match else full_version
            message = f"Installed: {display_version}\n\nThis version is not supported."
        else:
            message = "Minecraft Bedrock Edition not found.\n\nPlease install Minecraft from the Microsoft Store."
   
        ModernLabel(
            error_frame,
            text=message,
            font=("Segoe UI", 12),
            text_color=COLORS["text"],
            justify="center"
        ).pack(pady=15)
   
        supported_series = list(MinecraftVersionDetector.SUPPORTED_VERSION_SERIES.keys())
        display_names = [f"{s}0" for s in supported_series]
   
        ModernLabel(
            error_frame,
            text="Supported Versions:",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["accent"]
        ).pack(pady=(15, 8))
   
        ModernLabel(
            error_frame,
            text=", ".join(display_names),
            font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"],
            justify="center"
        ).pack(pady=8)
   
        self.protocol("WM_DELETE_WINDOW", self.safe_destroy)
    def start_version_monitoring(self):
        if self._is_closing:
            return
   
        def check_version():
            if self._is_closing:
                return
       
            version_check = MinecraftVersionDetector.check_compatibility()
       
            if version_check['supported']:
                self.update_queue.put(('version_compatible', version_check))
            else:
                self._version_check_timer = self.after(5000, check_version)
   
        self.after(100, check_version)
    def handle_version_compatible(self, version_check):
        if self._is_closing:
            return
   
        if self._version_check_timer:
            self.after_cancel(self._version_check_timer)
            self._version_check_timer = None
   
        self.minecraft_version = version_check['series_version']
        self.version_config = version_check['config']
   
        for widget in self.winfo_children():
            widget.destroy()
   
        self._initialize_main_app()
    def safe_destroy(self):
        if self._is_closing:
            return
        self._is_closing = True
   
        try:
            if self._version_check_timer:
                self.after_cancel(self._version_check_timer)
                self._version_check_timer = None
       
            for after_id in self.tk.call('after', 'info'):
                try:
                    self.after_cancel(after_id)
                except:
                    pass
       
            self.quit()
            self.destroy()
        except Exception as e:
            print(f"Error during window destruction: {e}")
            import sys
            sys.exit(0)
    def open_keybind_settings(self):
        if hasattr(self, 'keybind_window') and self.keybind_window and self.keybind_window.winfo_exists():
            self.keybind_window.lift()
            return
        keybind_window = KeybindWindow(self, self.config, update_callback=self.update_feature_titles)
        self.keybind_window = keybind_window
        if self.config.get_state("streamprotect"):
            keybind_window.attributes('-topmost', True)
        def on_close():
            self.streamprotect_controller.unregister_window("Keybind Settings")
            self.keybind_window = None
            keybind_window.destroy()
        keybind_window.protocol("WM_DELETE_WINDOW", on_close)
        if self.streamprotect_controller.initialized:
            def register():
                if keybind_window.winfo_exists():
                    hwnd = ctypes.windll.user32.FindWindowW(None, "Keybind Settings")
                    if hwnd != 0:
                        self.streamprotect_controller.register_window("Keybind Settings", hwnd)
            self.after(100, register)
    def update_feature_titles(self):
        for feature_key in ["brightness", "zoom"]:
            if feature_key in self.widgets["Visual"]:
                widget = self.widgets["Visual"][feature_key]
                if "title" in widget and "keybind_key" in widget:
                    keybind = widget["keybind_key"]
                    if keybind:
                        key = self.config.get_keybind(keybind)
                        base_title = widget["title"].cget("text").split(" (")[0]
                        new_title = f"{base_title} ({key.upper()})" if key else base_title
                        widget["title"].configure(text=new_title)
  
        if "sprint" in self.widgets["Movement"]:
            widget = self.widgets["Movement"]["sprint"]
            if "title" in widget and "keybind_key" in widget:
                keybind = widget["keybind_key"]
                if keybind:
                    key = self.config.get_keybind(keybind)
                    base_title = widget["title"].cget("text").split(" (")[0]
                    new_title = f"{base_title} ({key.upper()})" if key else base_title
                    widget["title"].configure(text=new_title)
  
        if "autoclicker" in self.widgets["Combat"]:
            widget = self.widgets["Combat"]["autoclicker"]
            left_key = self.config.get_keybind("autoclicker_left") or "z"
            right_key = self.config.get_keybind("autoclicker_right") or "x"
            new_title = f"AutoClicker (L:{left_key.upper()} R:{right_key.upper()})"
            widget["title"].configure(text=new_title)
      
            if self.autoclicker_controller.is_active:
                self.autoclicker_controller.set_keybinds(left_key, right_key)
                widget["status"].configure(
                    text=f"Active (L:{left_key.upper()} R:{right_key.upper()})",
                    text_color=COLORS["success"]
                )
    def create_loading_screen(self):
        self.loading_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        self.loading_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.92, relheight=0.92)
  
        self.loading_label = ModernLabel(self.loading_frame, text="Searching for Minecraft.Windows.exe...", font=("Segoe UI", 18, "bold"))
        self.loading_label.pack(pady=(140, 25))
  
        self.loading_circle = ctk.CTkProgressBar(self.loading_frame, orientation="horizontal", mode="indeterminate", width=240, height=4, fg_color=COLORS["border"], progress_color=COLORS["accent"], corner_radius=2)
        self.loading_circle.pack(pady=15)
        self.loading_circle.start()
  
        self.status_label = ModernLabel(self.loading_frame, text="Initializing...", text_color=COLORS["text_secondary"], font=("Segoe UI", 12))
        self.status_label.pack(pady=(15, 0))
  
        self.reconnect_button = ModernButton(self.loading_frame, text="Reconnect to Minecraft", command=self.start_initialization_thread)
        self.reconnect_button.pack_forget()
    def start_initialization_thread(self):
        version_check = MinecraftVersionDetector.check_compatibility()

        if not version_check['supported']:
            self.show_reconnect_screen(
                f"Incompatible version detected: {version_check['installed_version'] or 'Unknown'}\n"
                f"Please install a supported version."
            )
            return

        # バージョンが変更された場合の処理
        if version_check['series_version'] != self.minecraft_version:
            print(f"Version changed: {self.minecraft_version} -> {version_check['series_version']}")
            old_version = self.minecraft_version
            self.minecraft_version = version_check['series_version']
            self.version_config = version_check['config']
            self.title(f"Torio Client - Minecraft {self.minecraft_version}")
    
            if hasattr(self, 'hitbox_controller'):
                self.hitbox_controller.set_version_config(self.version_config)
            if hasattr(self, 'speed_controller'):
                self.speed_controller.set_version_config(self.version_config)
        
            # バージョン変更時にUIを再構築
            if hasattr(self, 'main_container') and self.main_container.winfo_exists():
                # 既存のコントローラーをリセット（バージョン固有のもの）
                if old_version == "1.21.13" and hasattr(self, 'nohurtcam_controller'):
                    if self.nohurtcam_controller.initialized:
                        self.nohurtcam_controller.reset_to_default(is_app_closing=True)
            
                # NoHurtCamコントローラーを再初期化
                self.nohurtcam_controller = NoHurtCamController()
            
                # ウィジェットを再構築
                self._rebuild_ui_for_version_change()

        self.show_loading_screen("Searching for Minecraft.Windows.exe...", COLORS["accent"])
        self.loading_thread = threading.Thread(target=self._initialize_backend, daemon=True)
        self.loading_thread.start()

    def _rebuild_ui_for_version_change(self):
        """バージョン変更時にUIを再構築する"""
        # Visual タブのウィジェットをクリア
        if "Visual" in self.widgets:
            # 既存のNoHurtCamウィジェットを削除
            if "nohurtcam" in self.widgets["Visual"]:
                self.widgets["Visual"]["nohurtcam"]["card"].destroy()
                del self.widgets["Visual"]["nohurtcam"]
    
        # Visual タブフレームを再構築
        if "Visual" in self.tab_frames:
            visual_frame = self.tab_frames["Visual"]
        
            # フレーム内の全ウィジェットを削除
            for widget in visual_frame.winfo_children():
                widget.destroy()
        
            # Visualタブを再作成
            self.create_visual_tab(visual_frame)
    
        # 現在Visualタブが表示されている場合は再描画
        if self.current_tab == "Visual":
            self.switch_tab("Visual")

    def _initialize_backend(self):
        try:
            self.update_queue.put(('status_text', "Searching for process..."))
            pm = pymem.Pymem("Minecraft.Windows.exe")
            self.game_process = pm
  
            self.antikb_controller.set_pymem_process(pm)
            self.antikb_controller.set_update_queue(self.update_queue)
            xz_mult = self.config.get_setting("antiknockback", "xz", 0.8)
            y_mult = self.config.get_setting("antiknockback", "y", 0.8)
            self.antikb_controller.kb_xz_mult = xz_mult
            self.antikb_controller.kb_y_mult = y_mult
  
            self.reach_controller.set_pymem_process(pm)
            self.reach_controller.set_update_queue(self.update_queue)
            reach_value = self.config.get_setting("reach", "reach", 3.0)
            self.reach_controller.current_reach = reach_value
  
            self.hitbox_controller.set_pymem_process(pm)
            self.hitbox_controller.set_version_config(self.version_config)
            self.hitbox_controller.set_update_queue(self.update_queue)
            hitbox_value = self.config.get_setting("hitbox", "hitbox", 1.0)
            self.hitbox_controller.current_hitbox = hitbox_value
  
            self.zoom_controller.set_pymem_process(pm)
            self.zoom_controller.set_update_queue(self.update_queue)
  
            self.brightness_controller.set_pymem_process(pm)
            self.brightness_controller.set_update_queue(self.update_queue)
   
            self.speed_controller.set_pymem_process(pm)
            self.speed_controller.set_version_config(self.version_config)
            self.speed_controller.set_update_queue(self.update_queue)
   
            self.coordinates_controller.set_pymem_process(pm)
            self.coordinates_controller.set_update_queue(self.update_queue)
   
            self.sprint_controller.set_pymem_process(pm)
            self.sprint_controller.set_update_queue(self.update_queue)

            self.truesight_controller.set_pymem_process(pm)
            self.truesight_controller.set_update_queue(self.update_queue)

            self.timechanger_controller.set_pymem_process(pm)
            self.timechanger_controller.set_update_queue(self.update_queue)
        
            # NoHurtCam初期化（1.21.13系統のみ）
            nohurtcam_init = False
            if self.minecraft_version == "1.21.13":
                self.nohurtcam_controller.set_pymem_process(pm)
                self.nohurtcam_controller.set_update_queue(self.update_queue)
  
            self.update_queue.put(('status_text', "Process found. Scanning memory..."))
  
            antikb_init = self.antikb_controller.initialize()
            reach_init = self.reach_controller.initialize()
            hitbox_init = self.hitbox_controller.initialize()
            zoom_init = self.zoom_controller.initialize()
            brightness_init = self.brightness_controller.initialize()
            speed_init = self.speed_controller.initialize()
            coordinates_init = self.coordinates_controller.initialize()
            sprint_init = self.sprint_controller.initialize()
            truesight_init = self.truesight_controller.initialize()
            timechanger_init = self.timechanger_controller.initialize()
        
            # NoHurtCam初期化実行（1.21.13系統のみ）
            if self.minecraft_version == "1.21.13":
                nohurtcam_init = self.nohurtcam_controller.initialize()
  
            if antikb_init or reach_init or hitbox_init or zoom_init or brightness_init or speed_init or coordinates_init or sprint_init or nohurtcam_init or truesight_init or timechanger_init:
                self.update_queue.put(('init_complete', True))
      
                if self.config.get_state("antiknockback") and antikb_init:
                    self.antikb_controller.start()
          
                if self.config.get_state("reach") and reach_init:
                    self.reach_controller.start()
      
                if self.config.get_state("hitbox") and hitbox_init:
                    self.hitbox_controller.start()
      
                if self.config.get_state("zoom") and zoom_init:
                    zoom_key = self.config.get_keybind("zoom") or "c"
                    self.zoom_controller.start(zoom_key)
      
                if self.config.get_state("brightness") and brightness_init:
                    self.brightness_controller.start()
       
                if self.config.get_state("speed") and speed_init:
                    speed_value = self.config.get_setting("speed", "speed", 0.5)
                    self.speed_controller.set_speed_value(speed_value)
                    self.speed_controller.start()
       
                if self.config.get_state("coordinates") and coordinates_init:
                    self.coordinates_controller.start()
       
                if self.config.get_state("sprint") and sprint_init:
                    sprint_key = self.config.get_keybind("sprint") or "p"
                    self.sprint_controller.current_key = sprint_key
                    self.sprint_controller.start()

                if self.config.get_state("truesight") and truesight_init:
                    self.truesight_controller.start()

                if self.config.get_state("timechanger") and timechanger_init:
                    time_value = self.config.get_setting("timechanger", "time", 1000)
                    self.timechanger_controller.set_time(time_value)
                    self.timechanger_controller.start()
                
                # NoHurtCam起動（1.21.13系統のみ）
                if self.minecraft_version == "1.21.13" and self.config.get_state("nohurtcam") and nohurtcam_init:
                    self.nohurtcam_controller.start()
            else:
                self.update_queue.put(('init_complete', False))
        except pymem.exception.ProcessNotFound:
            self.game_process = None
            self.update_queue.put(('init_complete', False))
        except Exception as e:
            print(f"Initialization Error: {e}")
            self.update_queue.put(('init_complete', False, f"Error: {e.__class__.__name__}"))

    def show_loading_screen(self, message, color):
        if hasattr(self, 'main_container') and self.main_container.winfo_exists():
            self.main_container.pack_forget()
        self.loading_frame.tkraise()
        self.loading_circle.start()
        self.loading_circle.configure(progress_color=color)
        self.loading_label.configure(text=message, text_color=color)
        self.status_label.configure(text="Please wait...", text_color=COLORS["text_secondary"])
        self.reconnect_button.pack_forget()
    def show_main_gui(self):
        self.loading_frame.lower()
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        self.apply_config_to_gui()
  
        main_hwnd = ctypes.windll.user32.FindWindowW(None, f"Torio Client - Minecraft {self.minecraft_version}")
        if main_hwnd != 0:
            self.streamprotect_controller.register_window("Torio Client", main_hwnd)
            self.streamprotect_controller.initialize()
      
            if self.config.get_state("streamprotect"):
                self.streamprotect_controller.start()
    def show_reconnect_screen(self, message):
        if hasattr(self, 'main_container') and self.main_container.winfo_exists():
            self.main_container.pack_forget()
        self.loading_frame.tkraise()
        self.loading_circle.stop()
        self.loading_circle.set(0)
        self.loading_label.configure(text="Connection Failed", text_color='#ff5252')
        self.status_label.configure(text=message, text_color=COLORS["text_secondary"])
        self.reconnect_button.pack(pady=20)
  
    def check_process_alive(self):
        if self.game_process and (self.antikb_controller.initialized or self.reach_controller.initialized or
                                   self.hitbox_controller.initialized or self.zoom_controller.initialized or
                                   self.brightness_controller.initialized or self.speed_controller.initialized or
                                   self.coordinates_controller.initialized or (self.minecraft_version == "1.21.13" and self.nohurtcam_controller.initialized)):
            antikb_valid = self.antikb_controller.validate_process() if self.antikb_controller.initialized else True
            reach_valid = self.reach_controller.validate_process() if self.reach_controller.initialized else True
            hitbox_valid = self.hitbox_controller.validate_process() if self.hitbox_controller.initialized else True
            zoom_valid = self.zoom_controller.validate_process() if self.zoom_controller.initialized else True
            brightness_valid = self.brightness_controller.validate_process() if self.brightness_controller.initialized else True
            speed_valid = self.speed_controller.validate_process() if self.speed_controller.initialized else True
            coordinates_valid = self.coordinates_controller.validate_process() if self.coordinates_controller.initialized else True
            sprint_valid = self.sprint_controller.validate_process() if self.sprint_controller.initialized else True
            truesight_valid = self.truesight_controller.validate_process() if self.truesight_controller.initialized else True
            timechanger_valid = self.timechanger_controller.validate_process() if self.timechanger_controller.initialized else True
            if self.minecraft_version == "1.21.13":
                nohurtcam_valid = self.nohurtcam_controller.validate_process() if self.nohurtcam_controller.initialized else True
            else:
                nohurtcam_valid = True
      
            if not antikb_valid or not reach_valid or not hitbox_valid or not zoom_valid or not brightness_valid or not speed_valid or not coordinates_valid or not sprint_valid or not nohurtcam_valid or not truesight_valid or not timechanger_valid:
                print("Process died. Resetting state.")
                self.antikb_controller.reset_to_default(is_app_closing=True)
                self.reach_controller.reset_to_default(is_app_closing=True)
                self.hitbox_controller.reset_to_default(is_app_closing=True)
                self.zoom_controller.reset_to_default(is_app_closing=True)
                self.brightness_controller.reset_to_default(is_app_closing=True)
                self.speed_controller.reset_to_default(is_app_closing=True)
                self.coordinates_controller.reset_to_default(is_app_closing=True)
                self.sprint_controller.reset_to_default(is_app_closing=True)
                self.truesight_controller.reset_to_default(is_app_closing=True)
                self.timechanger_controller.reset_to_default(is_app_closing=True)
                if self.minecraft_version == "1.21.13":
                    self.nohurtcam_controller.reset_to_default(is_app_closing=True)
                self.game_process = None
                self.show_reconnect_screen("Minecraft process has closed. Attempt reconnect.")
  
        self.check_process_timer = self.after(5000, self.check_process_alive)
    def process_queue(self):
        try:
            while True:
                item = self.update_queue.get_nowait()
                if item is None:
                    continue
          
                type = item[0]
          
                if type == 'version_compatible':
                    self.handle_version_compatible(item[1])
                    return
           
                elif type == 'init_complete':
                    success = item[1]
                    if success:
                        self.show_main_gui()
                    else:
                        error_msg = item[2] if len(item) > 2 else "Process not found or initialization error."
                        self.show_reconnect_screen(error_msg)
                  
                elif type == 'status_text':
                    self.status_label.configure(text=item[1])
              
                elif type == 'status_update':
                    feature_name, message, color = item[1]
              
                    if feature_name == "antiknockback" and feature_name in self.widgets["Movement"]:
                        self.widgets["Movement"][feature_name]["status"].configure(text=message, text_color=color)
                        if message == "Inactive":
                            self.widgets["Movement"][feature_name]["switch"].deselect()
                        elif message.startswith("Active"):
                            self.widgets["Movement"][feature_name]["switch"].select()
              
                    elif feature_name == "reach" and feature_name in self.widgets["Combat"]:
                        self.widgets["Combat"][feature_name]["status"].configure(text=message, text_color=color)
                        if message == "Inactive":
                            self.widgets["Combat"][feature_name]["switch"].deselect()
                        elif message.startswith("Active"):
                            self.widgets["Combat"][feature_name]["switch"].select()
              
                    elif feature_name == "hitbox" and feature_name in self.widgets["Combat"]:
                        self.widgets["Combat"][feature_name]["status"].configure(text=message, text_color=color)
                        if message == "Inactive":
                            self.widgets["Combat"][feature_name]["switch"].deselect()
                        elif message.startswith("Active"):
                            self.widgets["Combat"][feature_name]["switch"].select()
              
                    elif feature_name == "zoom" and feature_name in self.widgets["Visual"]:
                        self.widgets["Visual"][feature_name]["status"].configure(text=message, text_color=color)
                        if message == "Inactive":
                            self.widgets["Visual"][feature_name]["switch"].deselect()
                        elif message.startswith("Active"):
                            self.widgets["Visual"][feature_name]["switch"].select()
              
                    elif feature_name == "brightness" and feature_name in self.widgets["Visual"]:
                        self.widgets["Visual"][feature_name]["status"].configure(text=message, text_color=color)
                        if message == "Inactive":
                            self.widgets["Visual"][feature_name]["switch"].deselect()
                        elif message.startswith("Active"):
                            self.widgets["Visual"][feature_name]["switch"].select()
               
                    elif feature_name == "speed" and feature_name in self.widgets["Movement"]:
                        self.widgets["Movement"][feature_name]["status"].configure(text=message, text_color=color)
                        if message == "Inactive":
                            self.widgets["Movement"][feature_name]["switch"].deselect()
                        elif message.startswith("Active"):
                            self.widgets["Movement"][feature_name]["switch"].select()
               
                    elif feature_name == "coordinates" and feature_name in self.widgets["Visual"]:
                        self.widgets["Visual"][feature_name]["status"].configure(text=message, text_color=color)
                        if message == "Inactive":
                            self.widgets["Visual"][feature_name]["switch"].deselect()
                        elif message.startswith("Active"):
                            self.widgets["Visual"][feature_name]["switch"].select()
               
                    elif feature_name == "autoclicker" and feature_name in self.widgets["Combat"]:
                        self.widgets["Combat"][feature_name]["status"].configure(text=message, text_color=color)
                        if message == "Inactive":
                            self.widgets["Combat"][feature_name]["switch"].deselect()
                        elif message.startswith("Active"):
                            self.widgets["Combat"][feature_name]["switch"].select()
               
                    elif feature_name == "sprint" and feature_name in self.widgets["Movement"]:
                        self.widgets["Movement"][feature_name]["status"].configure(text=message, text_color=color)
                        if message == "Inactive":
                            self.widgets["Movement"][feature_name]["switch"].deselect()
                        elif message.startswith("Active"):
                            self.widgets["Movement"][feature_name]["switch"].select()

                    elif feature_name == "nohurtcam" and feature_name in self.widgets["Visual"]:
                        self.widgets["Visual"][feature_name]["status"].configure(text=message, text_color=color)
                        if message == "Inactive":
                            self.widgets["Visual"][feature_name]["switch"].deselect()
                        elif message.startswith("Active"):
                            self.widgets["Visual"][feature_name]["switch"].select()

                    elif feature_name == "truesight" and feature_name in self.widgets["Visual"]:
                        self.widgets["Visual"][feature_name]["status"].configure(text=message, text_color=color)
                        if message == "Inactive":
                            self.widgets["Visual"][feature_name]["switch"].deselect()
                        elif message.startswith("Active"):
                            self.widgets["Visual"][feature_name]["switch"].select()


                    elif feature_name == "timechanger" and feature_name in self.widgets["Visual"]:
                        self.widgets["Visual"][feature_name]["status"].configure(text=message, text_color=color)
                        if message == "Inactive":
                            self.widgets["Visual"][feature_name]["switch"].deselect()
                        elif message.startswith("Active"):
                            self.widgets["Visual"][feature_name]["switch"].select()
              
                    elif feature_name == "streamprotect" and feature_name in self.widgets["Misc"]:
                        self.widgets["Misc"][feature_name]["status"].configure(text=message, text_color=color)
                        if message == "Inactive" or message.startswith("Reset"):
                            self.widgets["Misc"][feature_name]["switch"].deselect()
                        elif message.startswith("Active"):
                            self.widgets["Misc"][feature_name]["switch"].select()
        except queue.Empty:
            pass
        finally:
            self.after(50, self.process_queue)
    def create_main_widgets(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        self.main_container.pack_forget()
    
        sidebar_frame = ModernFrame(self.main_container, width=200, fg_color=COLORS["surface"])
        sidebar_frame.pack(side="left", fill="both", pady=0, padx=(0, 10))
        sidebar_frame.pack_propagate(False)
        sidebar_frame.grid_columnconfigure(0, weight=1)
    
        content_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        content_frame.pack(side="right", fill="both", expand=True)
    
        title_container = ctk.CTkFrame(content_frame, fg_color="transparent")
        title_container.pack(pady=(5, 10), fill="x", anchor="w")
    
        ctk.CTkLabel(
            title_container,
            text="Torio Client",
            font=("Segoe UI", 26, "bold"),
            text_color=COLORS["accent"],
            anchor="w"
        ).pack(anchor="w", pady=(0, 2))
    
        ctk.CTkLabel(
            title_container,
            text="Minecraft Enhancement Suite",
            font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"],
            anchor="w"
        ).pack(anchor="w")
    
        icon_size = (24, 24)
        try:
            player_icon = ctk.CTkImage(light_image=Image.open(resource_path("icons/player.png")), size=icon_size)
            visual_icon = ctk.CTkImage(light_image=Image.open(resource_path("icons/visual.png")), size=icon_size)
            combat_icon = ctk.CTkImage(light_image=Image.open(resource_path("icons/combat.png")), size=icon_size)
            movement_icon = ctk.CTkImage(light_image=Image.open(resource_path("icons/movement.png")), size=icon_size)
            misc_icon = ctk.CTkImage(light_image=Image.open(resource_path("icons/misc.png")), size=icon_size)
        except:
            player_icon = visual_icon = combat_icon = movement_icon = misc_icon = None
    
        tabs = ["Player", "Visual", "Combat", "Movement", "Misc"]
        icons = {"Player": player_icon, "Visual": visual_icon, "Combat": combat_icon, "Movement": movement_icon, "Misc": misc_icon}
    
        for i in range(len(tabs)):
            sidebar_frame.grid_rowconfigure(i, weight=1)
    
        for i, tab in enumerate(tabs):
            label = ctk.CTkLabel(
                sidebar_frame,
                text=tab,
                font=("Segoe UI", 16, "bold"),
                text_color=COLORS["text_secondary"],
                image=icons.get(tab),
                compound="left",
                anchor="w",
                padx=16,
                height=60,
                corner_radius=8
            )
            label.grid(row=i, column=0, sticky="nsew", padx=8, pady=5)
            label.bind("<Button-1>", lambda e, t=tab: self.switch_tab(t))
            self.tab_labels[tab] = label
    
        self.tab_content_frame = ModernFrame(content_frame, fg_color=COLORS["surface"])
        self.tab_content_frame.pack(padx=0, pady=8, fill="both", expand=True)
    
        for tab in tabs:
            frame = ctk.CTkFrame(self.tab_content_frame, fg_color=COLORS["surface"])
            self.tab_frames[tab] = frame
            if tab == "Player":
                self.create_player_tab(frame)
            elif tab == "Visual":
                self.create_visual_tab(frame)
            elif tab == "Combat":
                self.create_combat_tab(frame)
            elif tab == "Movement":
                self.create_movement_tab(frame)
            elif tab == "Misc":
                self.create_misc_tab(frame)
    
        self.switch_tab("Player")
    
        controls = ModernFrame(content_frame)
        controls.pack(pady=(10, 5), fill="x")
        ModernButton(
            controls,
            text="Customize Keybinds",
            height=42,
            font=("Segoe UI", 13, "bold"),
            command=self.open_keybind_settings
        ).pack(pady=16, padx=16, fill="x")
    def create_feature_card(self, parent, title, feature_name, keybind_key=None):
        card = ModernFrame(parent, border_color=COLORS["border"])
        card.pack(pady=5, padx=10, fill="x")
    
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(pady=12, padx=16, fill="x")
        header.grid_columnconfigure(1, weight=1)
    
        key = self.config.get_keybind(keybind_key) if keybind_key else None
        title_text = title if not key else f"{title} ({key.upper()})"
        title_lbl = ModernLabel(header, text=title_text, font=("Segoe UI", 13, "bold"), anchor="w")
        title_lbl.grid(row=0, column=0, sticky="w")
    
        status_lbl = ModernLabel(header, text="Inactive", font=("Segoe UI", 11), text_color=COLORS["text_secondary"], anchor="w")
        status_lbl.grid(row=0, column=1, padx=(20, 0), sticky="w")
    
        switch = ModernSwitch(header, text="", command=lambda: self.toggle_feature(feature_name, status_lbl, switch))
        switch.grid(row=0, column=3, sticky="e", padx=(10, 0))
    
        return {"card": card, "status": status_lbl, "switch": switch, "title": title_lbl, "keybind_key": keybind_key}
    def create_slider_card(self, parent, title, feature_name, setting_key, minv, maxv, default, steps=100, keybind_key=None):
        card = ModernFrame(parent, border_color=COLORS["border"])
        card.pack(pady=5, padx=10, fill="x")
    
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 8))
        header.grid_columnconfigure(1, weight=1)
    
        key = self.config.get_keybind(keybind_key) if keybind_key else None
        title_text = title if not key else f"{title} ({key.upper()})"
        title_lbl = ModernLabel(header, text=title_text, font=("Segoe UI", 13, "bold"), anchor="w")
        title_lbl.grid(row=0, column=0, sticky="w")
    
        status_lbl = ModernLabel(header, text="Inactive", font=("Segoe UI", 11), text_color=COLORS["text_secondary"], anchor="w")
        status_lbl.grid(row=0, column=1, padx=(20, 0), sticky="w")
    
        switch = ModernSwitch(header, text="", command=lambda: self.toggle_feature(feature_name, status_lbl, switch))
        switch.grid(row=0, column=3, sticky="e", padx=(10, 0))
    
        slider_frame = ctk.CTkFrame(card, fg_color="transparent")
        slider_frame.pack(fill="x", padx=16, pady=(5, 12))
    
        val_lbl = ModernLabel(slider_frame, text=f"Value: {default:.2f}", font=("Segoe UI", 11), text_color=COLORS["accent"], anchor="w")
        val_lbl.pack(anchor="w", pady=(0, 8))
    
        def slider_command(v, feature=feature_name, key=setting_key, label=val_lbl):
            val = float(v)
            label.configure(text=f"Value: {val:.2f}")
            self.config.set_setting(feature, key, val)
      
            if feature == "reach":
                if self.reach_controller:
                    self.reach_controller.set_reach_value(val)
            elif feature == "hitbox":
                if self.hitbox_controller:
                    self.hitbox_controller.set_hitbox_value(val)
            elif feature == "speed":
                if self.speed_controller:
                    self.speed_controller.set_speed_value(val)
    
        slider = ModernSlider(slider_frame, from_=minv, to=maxv, number_of_steps=steps, width=380,
                              command=slider_command)
        slider.pack(fill="x")
    
        rng = ctk.CTkFrame(slider_frame, fg_color="transparent")
        rng.pack(fill="x", pady=(4, 0))
        ModernLabel(rng, text=str(minv), font=("Segoe UI", 9), text_color=COLORS["text_secondary"]).pack(side="left")
        ModernLabel(rng, text=str(maxv), font=("Segoe UI", 9), text_color=COLORS["text_secondary"]).pack(side="right")
    
        return {"card": card, "status": status_lbl, "switch": switch, "slider": slider, "value_label": val_lbl, "title": title_lbl, "keybind_key": keybind_key}
    def create_autoclicker_card(self, parent):
        card = ModernFrame(parent, border_color=COLORS["border"])
        card.pack(pady=5, padx=10, fill="x")
    
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 8))
        header.grid_columnconfigure(1, weight=1)
    
        left_key = self.config.get_keybind("autoclicker_left") or "z"
        right_key = self.config.get_keybind("autoclicker_right") or "x"
        title_text = f"AutoClicker (L:{left_key.upper()} R:{right_key.upper()})"
  
        title_lbl = ModernLabel(header, text=title_text, font=("Segoe UI", 13, "bold"), anchor="w")
        title_lbl.grid(row=0, column=0, sticky="w")
    
        status_lbl = ModernLabel(header, text="Inactive", font=("Segoe UI", 11), text_color=COLORS["text_secondary"], anchor="w")
        status_lbl.grid(row=0, column=1, padx=(20, 0), sticky="w")
    
        switch = ModernSwitch(header, text="", command=lambda: self.toggle_feature("autoclicker", status_lbl, switch))
        switch.grid(row=0, column=3, sticky="e", padx=(10, 0))
    
        left_cps_frame = ctk.CTkFrame(card, fg_color="transparent")
        left_cps_frame.pack(fill="x", padx=16, pady=6)
    
        left_cps_val_lbl = ModernLabel(left_cps_frame, text="Left CPS: 10.0", font=("Segoe UI", 11), text_color=COLORS["accent"], anchor="w")
        left_cps_val_lbl.pack(anchor="w", pady=(0, 8))
  
        def left_cps_slider_command(v):
            val = float(v)
            left_cps_val_lbl.configure(text=f"Left CPS: {val:.1f}")
            self.config.set_setting("autoclicker", "left_cps", val)
            if self.autoclicker_controller.is_active:
                right_cps = self.config.get_setting("autoclicker", "right_cps", 10.0)
                self.autoclicker_controller.set_cps(val, right_cps)
        left_cps_slider = ModernSlider(left_cps_frame, from_=1.0, to=20.0, number_of_steps=190, width=380,
                                command=left_cps_slider_command)
        left_cps_slider.pack(fill="x")
        right_cps_frame = ctk.CTkFrame(card, fg_color="transparent")
        right_cps_frame.pack(fill="x", padx=16, pady=6)
        right_cps_val_lbl = ModernLabel(right_cps_frame, text="Right CPS: 10.0", font=("Segoe UI", 11), text_color=COLORS["accent"], anchor="w")
        right_cps_val_lbl.pack(anchor="w", pady=(0, 8))
  
        def right_cps_slider_command(v):
            val = float(v)
            right_cps_val_lbl.configure(text=f"Right CPS: {val:.1f}")
            self.config.set_setting("autoclicker", "right_cps", val)
            if self.autoclicker_controller.is_active:
                left_cps = self.config.get_setting("autoclicker", "left_cps", 10.0)
                self.autoclicker_controller.set_cps(left_cps, val)
        right_cps_slider = ModernSlider(right_cps_frame, from_=1.0, to=20.0, number_of_steps=190, width=380,
                                 command=right_cps_slider_command)
        right_cps_slider.pack(fill="x")
        chk_frame = ctk.CTkFrame(card, fg_color="transparent")
        chk_frame.pack(fill="x", padx=16, pady=(6, 12))
        left_var = ctk.BooleanVar(value=self.config.get_setting("autoclicker", "left_enabled", True))
        right_var = ctk.BooleanVar(value=self.config.get_setting("autoclicker", "right_enabled", True))
    
        def left_checkbox_command():
            enabled = left_var.get()
            self.config.set_setting("autoclicker", "left_enabled", enabled)
            if self.autoclicker_controller.is_active:
                self.autoclicker_controller.set_click_enabled(enabled, right_var.get())
    
        def right_checkbox_command():
            enabled = right_var.get()
            self.config.set_setting("autoclicker", "right_enabled", enabled)
            if self.autoclicker_controller.is_active:
                self.autoclicker_controller.set_click_enabled(left_var.get(), enabled)
        ModernCheckBox(chk_frame, text="Left Click", variable=left_var,
                        command=left_checkbox_command).pack(side="left", padx=(0, 24))
        ModernCheckBox(chk_frame, text="Right Click", variable=right_var,
                        command=right_checkbox_command).pack(side="left")
        return {
            "card": card,
            "status": status_lbl,
            "switch": switch,
            "left_slider": left_cps_slider,
            "right_slider": right_cps_slider,
            "left_value_label": left_cps_val_lbl,
            "right_value_label": right_cps_val_lbl,
            "title": title_lbl,
            "left_var": left_var,
            "right_var": right_var
        }
    def create_antiknockback_card(self, parent):
        card = ModernFrame(parent, border_color=COLORS["border"])
        card.pack(pady=5, padx=10, fill="x")
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 8))
        header.grid_columnconfigure(1, weight=1)
        title_lbl = ModernLabel(header, text="AntiKnockback", font=("Segoe UI", 13, "bold"), anchor="w")
        title_lbl.grid(row=0, column=0, sticky="w")
        status_lbl = ModernLabel(header, text="Inactive", font=("Segoe UI", 11), text_color=COLORS["text_secondary"], anchor="w")
        status_lbl.grid(row=0, column=1, padx=(20, 0), sticky="w")
        switch = ModernSwitch(header, text="", command=lambda: self.toggle_feature("antiknockback", status_lbl, switch))
        switch.grid(row=0, column=3, sticky="e", padx=(10, 0))
        xz_frame = ctk.CTkFrame(card, fg_color="transparent")
        xz_frame.pack(fill="x", padx=16, pady=6)
        xz_lbl = ModernLabel(xz_frame, text="X/Z: 0.80", font=("Segoe UI", 11), text_color=COLORS["accent"], anchor="w")
        xz_lbl.pack(anchor="w", pady=(0, 8))
  
        def xz_slider_command(v):
            val = float(v)
            xz_lbl.configure(text=f"X/Z: {val:.2f}")
            self.config.set_setting("antiknockback", "xz", val)
            if self.antikb_controller:
                current_y = self.config.get_setting("antiknockback", "y", 0.8)
                self.antikb_controller.set_multipliers(val, current_y)
        xz_slider = ModernSlider(xz_frame, from_=0.0, to=2.0, number_of_steps=200, width=380,
                                 command=xz_slider_command)
        xz_slider.pack(fill="x")
        y_frame = ctk.CTkFrame(card, fg_color="transparent")
        y_frame.pack(fill="x", padx=16, pady=(6, 12))
        y_lbl = ModernLabel(y_frame, text="Y: 0.80", font=("Segoe UI", 11), text_color=COLORS["accent"], anchor="w")
        y_lbl.pack(anchor="w", pady=(0, 8))

        def y_slider_command(v):
            val = float(v)
            y_lbl.configure(text=f"Y: {val:.2f}")
            self.config.set_setting("antiknockback", "y", val)
            if self.antikb_controller:
                current_xz = self.config.get_setting("antiknockback", "xz", 0.8)
                self.antikb_controller.set_multipliers(current_xz, val)
        y_slider = ModernSlider(y_frame, from_=0.0, to=2.0, number_of_steps=200, width=380,
                                command=y_slider_command)
        y_slider.pack(fill="x")
        return {"card": card, "status": status_lbl, "switch": switch, "xz_slider": xz_slider, "y_slider": y_slider, "xz_label": xz_lbl, "y_label": y_lbl}
    def create_visual_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        w = self.create_feature_card(parent, "Fullbright", "brightness", "brightness")
        self.widgets["Visual"]["brightness"] = w
        w = self.create_feature_card(parent, "Zoom", "zoom", "zoom")
        self.widgets["Visual"]["zoom"] = w
        w = self.create_feature_card(parent, "Coordinates", "coordinates")
        self.widgets["Visual"]["coordinates"] = w
        w = self.create_feature_card(parent, "TrueSight", "truesight")
        self.widgets["Visual"]["truesight"] = w
        w = self.create_timechanger_card(parent)
        self.widgets["Visual"]["timechanger"] = w
        if self.minecraft_version == "1.21.13":
            w = self.create_feature_card(parent, "No Hurt Cam", "nohurtcam")
            self.widgets["Visual"]["nohurtcam"] = w
    def create_combat_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        w = self.create_slider_card(parent, "Reach", "reach", "reach", 3.0, 7.0, 3.0, steps=40)
        self.widgets["Combat"]["reach"] = w
        w = self.create_autoclicker_card(parent)
        self.widgets["Combat"]["autoclicker"] = w
        w = self.create_slider_card(parent, "Hitbox", "hitbox", "hitbox", 1.0, 2.0, 1.0, steps=100)
        self.widgets["Combat"]["hitbox"] = w
    def create_movement_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        w = self.create_feature_card(parent, "Toggle Sprint", "sprint", "sprint")
        self.widgets["Movement"]["sprint"] = w
        w = self.create_slider_card(parent, "Speed Hack", "speed", "speed", 0.5, 5.0, 0.5, steps=45)
        self.widgets["Movement"]["speed"] = w
        w = self.create_antiknockback_card(parent)
        self.widgets["Movement"]["antiknockback"] = w
    def create_timechanger_card(self, parent):
        card = ModernFrame(parent, border_color=COLORS["border"])
        card.pack(pady=5, padx=10, fill="x")
    
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 8))
        header.grid_columnconfigure(1, weight=1)
    
        title_lbl = ModernLabel(header, text="Time Changer", font=("Segoe UI", 13, "bold"), anchor="w")
        title_lbl.grid(row=0, column=0, sticky="w")
    
        status_lbl = ModernLabel(header, text="Inactive", font=("Segoe UI", 11), text_color=COLORS["text_secondary"], anchor="w")
        status_lbl.grid(row=0, column=1, padx=(20, 0), sticky="w")
    
        switch = ModernSwitch(header, text="", command=lambda: self.toggle_feature("timechanger", status_lbl, switch))
        switch.grid(row=0, column=3, sticky="e", padx=(10, 0))

        preset_frame = ctk.CTkFrame(card, fg_color="transparent")
        preset_frame.pack(fill="x", padx=16, pady=6)
    
        preset_options = ["Day", "Noon", "Sunset", "Night", "Midnight", "Sunrise"]
        preset_var = ctk.StringVar(value="Day")
    
        def preset_changed(choice):
            time_value = self.timechanger_controller.TIME_PRESETS[choice]
            self.config.set_setting("timechanger", "time", time_value)
            self.config.set_setting("timechanger", "preset", choice)
            slider.set(time_value)
            time_lbl.configure(text=f"Time: {int(time_value)} ({choice})")
            if self.timechanger_controller.is_active:
                self.timechanger_controller.set_time(time_value)
    
        preset_dropdown = ctk.CTkOptionMenu(
            preset_frame,
            variable=preset_var,
            values=preset_options,
            command=preset_changed,
            fg_color=COLORS["accent"],
            button_color=COLORS["accent_dark"],
            button_hover_color=COLORS["accent_light"],
            dropdown_fg_color=COLORS["card"],
            dropdown_hover_color=COLORS["card_hover"],
            font=("Segoe UI", 12),
            dropdown_font=("Segoe UI", 11),
            width=380
        )
        preset_dropdown.pack(fill="x")
    
        # Time slider
        slider_frame = ctk.CTkFrame(card, fg_color="transparent")
        slider_frame.pack(fill="x", padx=16, pady=(10, 12))
    
        default_time = self.config.get_setting("timechanger", "time", 1000)
        time_lbl = ModernLabel(slider_frame, text=f"Time: {int(default_time)} (Day)", font=("Segoe UI", 11), text_color=COLORS["accent"], anchor="w")
        time_lbl.pack(anchor="w", pady=(0, 8))
    
        def slider_command(v):
            val = int(v)
            # Find closest preset name
            preset_name = "Custom"
            for name, preset_val in self.timechanger_controller.TIME_PRESETS.items():
                if abs(preset_val - val) < 100:  # Within 100 ticks
                    preset_name = name
                    preset_var.set(name)
                    break
        
            display_text = f"Time: {val}" + (f" ({preset_name})" if preset_name != "Custom" else "")
            time_lbl.configure(text=display_text)
            self.config.set_setting("timechanger", "time", val)
        
            if self.timechanger_controller.is_active:
                self.timechanger_controller.set_time(val)
    
        slider = ModernSlider(slider_frame, from_=0, to=24000, number_of_steps=240, width=380, command=slider_command)
        slider.pack(fill="x")
    
        rng = ctk.CTkFrame(slider_frame, fg_color="transparent")
        rng.pack(fill="x", pady=(4, 0))
        ModernLabel(rng, text="0", font=("Segoe UI", 9), text_color=COLORS["text_secondary"]).pack(side="left")
        ModernLabel(rng, text="24000", font=("Segoe UI", 9), text_color=COLORS["text_secondary"]).pack(side="right")
    
        return {
            "card": card,
            "status": status_lbl,
            "switch": switch,
            "slider": slider,
            "time_label": time_lbl,
            "preset_var": preset_var,
            "preset_dropdown": preset_dropdown
        }
    def create_misc_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        w = self.create_feature_card(parent, "Streamprotect", "streamprotect")
        self.widgets["Misc"]["streamprotect"] = w
    def create_player_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
    
        empty = ModernFrame(parent, border_color=COLORS["border"])
        empty.pack(pady=50, padx=10, fill="x")
    
        ModernLabel(
            empty,
            text="Player",
            font=("Segoe UI", 18, "bold"),
            text_color=COLORS["accent"],
            anchor="w"
        ).pack(pady=(20, 8), padx=20, anchor="w")
    
        ModernLabel(
            empty,
            text="Player features coming soon...",
            font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"],
            anchor="w"
        ).pack(pady=(5, 20), padx=20, anchor="w")
    def switch_tab(self, tab_name):
        for name, lbl in self.tab_labels.items():
            if name == tab_name:
                lbl.configure(fg_color=COLORS["sidebar_active"], text_color=COLORS["text"])
            else:
                lbl.configure(fg_color="transparent", text_color=COLORS["text_secondary"])
    
        for frame in self.tab_frames.values():
            frame.pack_forget()
    
        self.current_tab = tab_name
        self.tab_frames[tab_name].pack(fill="both", expand=True, padx=12, pady=12)
    def toggle_feature(self, feature_name, status_label, switch):
        state = switch.get() == 1
        self.config.set_state(feature_name, state)
  
        if feature_name == "antiknockback":
            if not self.game_process:
                switch.deselect()
                status_label.configure(text="Inactive (No Process)", text_color='#ff5252')
                self.config.set_state(feature_name, False)
                return
            if state:
                xz_value = self.config.get_setting("antiknockback", "xz", 0.8)
                y_value = self.config.get_setting("antiknockback", "y", 0.8)
                self.antikb_controller.set_multipliers(xz_value, y_value)
                self.antikb_controller.start()
                status_label.configure(text="Activating...", text_color=COLORS["accent"])
            else:
                self.antikb_controller.stop()
                status_label.configure(text="Deactivating...", text_color=COLORS["text_secondary"])
  
        elif feature_name == "reach":
            if not self.game_process:
                switch.deselect()
                status_label.configure(text="Inactive (No Process)", text_color='#ff5252')
                self.config.set_state(feature_name, False)
                return
      
            if state:
                reach_value = self.config.get_setting("reach", "reach", 3.0)
                self.reach_controller.set_reach_value(reach_value)
                self.reach_controller.start()
                status_label.configure(text="Activating...", text_color=COLORS["accent"])
            else:
                self.reach_controller.stop()
                status_label.configure(text="Deactivating...", text_color=COLORS["text_secondary"])
  
        elif feature_name == "hitbox":
            if not self.game_process:
                switch.deselect()
                status_label.configure(text="Inactive (No Process)", text_color='#ff5252')
                self.config.set_state(feature_name, False)
                return
      
            if state:
                hitbox_value = self.config.get_setting("hitbox", "hitbox", 1.0)
                self.hitbox_controller.set_hitbox_value(hitbox_value)
                self.hitbox_controller.start()
                status_label.configure(text="Activating...", text_color=COLORS["accent"])
            else:
                self.hitbox_controller.stop()
                status_label.configure(text="Deactivating...", text_color=COLORS["text_secondary"])
  
        elif feature_name == "zoom":
            if not self.game_process:
                switch.deselect()
                status_label.configure(text="Inactive (No Process)", text_color='#ff5252')
                self.config.set_state(feature_name, False)
                return
      
            if state:
                zoom_key = self.config.get_keybind("zoom") or "c"
                self.zoom_controller.start(zoom_key)
                status_label.configure(text="Activating...", text_color=COLORS["accent"])
            else:
                self.zoom_controller.stop()
                status_label.configure(text="Deactivating...", text_color=COLORS["text_secondary"])
  
        elif feature_name == "brightness":
            if not self.game_process:
                switch.deselect()
                status_label.configure(text="Inactive (No Process)", text_color='#ff5252')
                self.config.set_state(feature_name, False)
                return
      
            if state:
                self.brightness_controller.start()
                status_label.configure(text="Activating...", text_color=COLORS["accent"])
            else:
                self.brightness_controller.stop()
                status_label.configure(text="Deactivating...", text_color=COLORS["text_secondary"])
   
        elif feature_name == "speed":
            if not self.game_process:
                switch.deselect()
                status_label.configure(text="Inactive (No Process)", text_color='#ff5252')
                self.config.set_state(feature_name, False)
                return
      
            if state:
                speed_value = self.config.get_setting("speed", "speed", 0.5)
                self.speed_controller.set_speed_value(speed_value)
                self.speed_controller.start()
                status_label.configure(text="Activating...", text_color=COLORS["accent"])
            else:
                self.speed_controller.stop()
                status_label.configure(text="Deactivating...", text_color=COLORS["text_secondary"])
   
        elif feature_name == "coordinates":
            if not self.game_process:
                switch.deselect()
                status_label.configure(text="Inactive (No Process)", text_color='#ff5252')
                self.config.set_state(feature_name, False)
                return
            if state:
                self.coordinates_controller.start()
                status_label.configure(text="Activating...", text_color=COLORS["accent"])
            else:
                self.coordinates_controller.stop()
                status_label.configure(text="Deactivating...", text_color=COLORS["text_secondary"])
   
        elif feature_name == "autoclicker":
            if state:
                left_cps = self.config.get_setting("autoclicker", "left_cps", 10.0)
                right_cps = self.config.get_setting("autoclicker", "right_cps", 10.0)
                left_enabled = self.config.get_setting("autoclicker", "left_enabled", True)
                right_enabled = self.config.get_setting("autoclicker", "right_enabled", True)
                left_key = self.config.get_keybind("autoclicker_left") or "z"
                right_key = self.config.get_keybind("autoclicker_right") or "x"
          
                self.autoclicker_controller.set_cps(left_cps, right_cps)
                self.autoclicker_controller.set_click_enabled(left_enabled, right_enabled)
                self.autoclicker_controller.set_keybinds(left_key, right_key)
                self.autoclicker_controller.start()
                status_label.configure(text="Activating...", text_color=COLORS["accent"])
            else:
                self.autoclicker_controller.stop()
                status_label.configure(text="Deactivating...", text_color=COLORS["text_secondary"])
   
        elif feature_name == "sprint":
            if not self.game_process:
                switch.deselect()
                status_label.configure(text="Inactive (No Process)", text_color='#ff5252')
                self.config.set_state(feature_name, False)
                return
            if state:
                sprint_key = self.config.get_keybind("sprint") or "p"
                self.sprint_controller.current_key = sprint_key
                self.sprint_controller.start()
                status_label.configure(text="Activating...", text_color=COLORS["accent"])
            else:
                self.sprint_controller.stop()
                status_label.configure(text="Deactivating...", text_color=COLORS["text_secondary"])


        elif feature_name == "nohurtcam":
            if not self.game_process:
                switch.deselect()
                status_label.configure(text="Inactive (No Process)", text_color='#ff5252')
                self.config.set_state(feature_name, False)
                return
            if state:
                self.nohurtcam_controller.start()
                status_label.configure(text="Activating...", text_color=COLORS["accent"])
            else:
                self.nohurtcam_controller.stop()
                status_label.configure(text="Deactivating...", text_color=COLORS["text_secondary"])

        elif feature_name == "truesight":
            if not self.game_process:
                switch.deselect()
                status_label.configure(text="Inactive (No Process)", text_color='#ff5252')
                self.config.set_state(feature_name, False)
                return
            if state:
                self.truesight_controller.start()
                status_label.configure(text="Activating...", text_color=COLORS["accent"])
            else:
                self.truesight_controller.stop()
                status_label.configure(text="Deactivating...", text_color=COLORS["text_secondary"])

        elif feature_name == "timechanger":
            if not self.game_process:
                switch.deselect()
                status_label.configure(text="Inactive (No Process)", text_color='#ff5252')
                self.config.set_state(feature_name, False)
                return
            if state:
                time_value = self.config.get_setting("timechanger", "time", 1000)
                self.timechanger_controller.set_time(time_value)
                self.timechanger_controller.start()
                status_label.configure(text="Activating...", text_color=COLORS["accent"])
            else:
                self.timechanger_controller.stop()
                status_label.configure(text="Deactivating...", text_color=COLORS["text_secondary"])
  
        elif feature_name == "streamprotect":
            if not self.streamprotect_controller.initialized:
                switch.deselect()
                status_label.configure(text="Not initialized", text_color='#ff9800')
                self.config.set_state(feature_name, False)
                return
            if state:
                self.streamprotect_controller.start()
                self.attributes('-topmost', True)
                if hasattr(self, 'keybind_window') and self.keybind_window and self.keybind_window.winfo_exists():
                    self.keybind_window.attributes('-topmost', True)
                status_label.configure(text="Active (Protected)", text_color=COLORS["success"])
            else:
                self.streamprotect_controller.stop()
                self.attributes('-topmost', False)
                if hasattr(self, 'keybind_window') and self.keybind_window and self.keybind_window.winfo_exists():
                    self.keybind_window.attributes('-topmost', False)
                status_label.configure(text="Inactive", text_color=COLORS["text_secondary"])
    def apply_config_to_gui(self):
        c = self.config
  
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
   
        for f in ["coordinates"]:
            if f in self.widgets["Visual"]:
                w = self.widgets["Visual"][f]
                if c.get_state(f):
                    w["switch"].select()
                    w["status"].configure(text="Active", text_color=COLORS["success"])
  
        if "brightness" in self.widgets["Visual"]:
            w_brightness = self.widgets["Visual"]["brightness"]
            if c.get_state("brightness"):
                w_brightness["switch"].select()
                w_brightness["status"].configure(text="Inactive (Loading...)", text_color=COLORS["text_secondary"])
  
        if "zoom" in self.widgets["Visual"]:
            w_zoom = self.widgets["Visual"]["zoom"]
            if c.get_state("zoom"):
                w_zoom["switch"].select()
                w_zoom["status"].configure(text="Inactive (Loading...)", text_color=COLORS["text_secondary"])
   
        if "coordinates" in self.widgets["Visual"]:
            w_coordinates = self.widgets["Visual"]["coordinates"]
            if c.get_state("coordinates"):
                w_coordinates["switch"].select()
                w_coordinates["status"].configure(text="Inactive (Loading...)", text_color=COLORS["text_secondary"])
   
        w_reach = self.widgets["Combat"]["reach"]
        if c.get_state("reach"):
            w_reach["switch"].select()
            w_reach["status"].configure(text="Inactive (Loading...)", text_color=COLORS["text_secondary"])
        reach_value = c.get_setting("reach", "reach", 3.0)
        w_reach["slider"].set(reach_value)
        w_reach["value_label"].configure(text=f"Value: {reach_value:.2f}")
   
        w_hitbox = self.widgets["Combat"]["hitbox"]
        if c.get_state("hitbox"):
            w_hitbox["switch"].select()
            w_hitbox["status"].configure(text="Inactive (Loading...)", text_color=COLORS["text_secondary"])
        hitbox_value = c.get_setting("hitbox", "hitbox", 1.0)
        w_hitbox["slider"].set(hitbox_value)
        w_hitbox["value_label"].configure(text=f"Value: {hitbox_value:.2f}")
   
        w_autoclicker = self.widgets["Combat"]["autoclicker"]
  
        left_cps_value = self.config.get_setting("autoclicker", "left_cps", 10.0)
        right_cps_value = self.config.get_setting("autoclicker", "right_cps", 10.0)
        w_autoclicker["left_slider"].set(left_cps_value)
        w_autoclicker["right_slider"].set(right_cps_value)
        w_autoclicker["left_value_label"].configure(text=f"Left CPS: {left_cps_value:.1f}")
        w_autoclicker["right_value_label"].configure(text=f"Right CPS: {right_cps_value:.1f}")
  
        left_enabled = self.config.get_setting("autoclicker", "left_enabled", True)
        right_enabled = self.config.get_setting("autoclicker", "right_enabled", True)
        w_autoclicker["left_var"].set(left_enabled)
        w_autoclicker["right_var"].set(right_enabled)
  
        if self.config.get_state("autoclicker"):
            w_autoclicker["switch"].select()
      
            left_key = self.config.get_keybind("autoclicker_left") or "z"
            right_key = self.config.get_keybind("autoclicker_right") or "x"
      
            self.autoclicker_controller.set_cps(left_cps_value, right_cps_value)
            self.autoclicker_controller.set_click_enabled(left_enabled, right_enabled)
            self.autoclicker_controller.set_keybinds(left_key, right_key)
            self.autoclicker_controller.start()
      
            w_autoclicker["status"].configure(
                text=f"Active (L:{left_key.upper()} R:{right_key.upper()})",
                text_color=COLORS["success"]
            )
        else:
            w_autoclicker["status"].configure(text="Inactive", text_color=COLORS["text_secondary"])
   
        w_sprint = self.widgets["Movement"]["sprint"]
        if c.get_state("sprint"):
            w_sprint["switch"].select()
            w_sprint["status"].configure(text="Inactive (Loading...)", text_color=COLORS["text_secondary"])
   
        w_speed = self.widgets["Movement"]["speed"]
        if c.get_state("speed"):
            w_speed["switch"].select()
            w_speed["status"].configure(text="Inactive (Loading...)", text_color=COLORS["text_secondary"])
        speed_value = c.get_setting("speed", "speed", 0.5)
        w_speed["slider"].set(speed_value)
        w_speed["value_label"].configure(text=f"Value: {speed_value:.2f}")
   
        w_antikb = self.widgets["Movement"]["antiknockback"]
        xz_value = c.get_setting("antiknockback", "xz", 0.8)
        y_value = c.get_setting("antiknockback", "y", 0.8)
  
        w_antikb["xz_slider"].set(xz_value)
        w_antikb["y_slider"].set(y_value)
        w_antikb["xz_label"].configure(text=f"X/Z: {xz_value:.2f}")
        w_antikb["y_label"].configure(text=f"Y: {y_value:.2f}")
  
        if c.get_state("antiknockback"):
            w_antikb["switch"].select()
            w_antikb["status"].configure(text="Inactive (Loading...)", text_color=COLORS["text_secondary"])
        else:
            w_antikb["switch"].deselect()
            w_antikb["status"].configure(text="Inactive", text_color=COLORS["text_secondary"])
   
        if self.minecraft_version == "1.21.13" and "nohurtcam" in self.widgets["Visual"]:
            w_nohurtcam = self.widgets["Visual"]["nohurtcam"]
            if c.get_state("nohurtcam"):
                w_nohurtcam["switch"].select()
                w_nohurtcam["status"].configure(text="Inactive (Loading...)", text_color=COLORS["text_secondary"])
            else:
                w_nohurtcam["switch"].deselect()
                w_nohurtcam["status"].configure(text="Inactive", text_color=COLORS["text_secondary"])

        w_streamprotect = self.widgets["Misc"]["streamprotect"]
        if c.get_state("streamprotect"):
            w_streamprotect["switch"].select()
            w_streamprotect["status"].configure(text="Inactive (Loading...)", text_color=COLORS["text_secondary"])
            self.attributes('-topmost', True)
        else:
            w_streamprotect["switch"].deselect()
            self.attributes('-topmost', False)

        if "truesight" in self.widgets["Visual"]:
            w_truesight = self.widgets["Visual"]["truesight"]
            if c.get_state("truesight"):
                w_truesight["switch"].select()
                w_truesight["status"].configure(text="Inactive (Loading...)", text_color=COLORS["text_secondary"])
            else:
                w_truesight["switch"].deselect()

        if "timechanger" in self.widgets["Visual"]:
            w_timechanger = self.widgets["Visual"]["timechanger"]
            time_value = self.config.get_setting("timechanger", "time", 1000)
            preset_name = self.config.get_setting("timechanger", "preset", "Day")
    
            w_timechanger["slider"].set(time_value)
            w_timechanger["preset_var"].set(preset_name)
            w_timechanger["time_label"].configure(text=f"Time: {int(time_value)} ({preset_name})")
    
            if self.config.get_state("timechanger"):
                w_timechanger["switch"].select()
                w_timechanger["status"].configure(text="Inactive (Loading...)", text_color=COLORS["text_secondary"])
            else:
                w_timechanger["switch"].deselect()

    def on_closing(self):
        self._is_closing = True
   
        if self._version_check_timer:
            self.after_cancel(self._version_check_timer)
   
        if hasattr(self, 'check_process_timer') and self.check_process_timer:
            self.after_cancel(self.check_process_timer)
        if hasattr(self, 'antikb_controller') and self.antikb_controller and self.antikb_controller.initialized:
            if self.antikb_controller.is_active:
                self.antikb_controller.disable_antiknockback()
            self.antikb_controller.reset_to_default(is_app_closing=True)
        if hasattr(self, 'reach_controller') and self.reach_controller and self.reach_controller.initialized:
            if self.reach_controller.is_active:
                self.reach_controller.disable_reach()
            self.reach_controller.reset_to_default(is_app_closing=True)
        if hasattr(self, 'hitbox_controller') and self.hitbox_controller and self.hitbox_controller.initialized:
            if self.hitbox_controller.is_active:
                self.hitbox_controller.disable_hitbox()
            self.hitbox_controller.reset_to_default(is_app_closing=True)
  
        if hasattr(self, 'zoom_controller') and self.zoom_controller and self.zoom_controller.initialized:
            if self.zoom_controller.is_active:
                self.zoom_controller.stop(is_app_closing=True)
            self.zoom_controller.reset_to_default(is_app_closing=True)
  
        if hasattr(self, 'brightness_controller') and self.brightness_controller and self.brightness_controller.initialized:
            if self.brightness_controller.is_active:
                self.brightness_controller.stop(is_app_closing=True)
            self.brightness_controller.reset_to_default(is_app_closing=True)
   
        if hasattr(self, 'coordinates_controller') and self.coordinates_controller and self.coordinates_controller.initialized:
            if self.coordinates_controller.is_active:
                self.coordinates_controller.stop(is_app_closing=True)
            self.coordinates_controller.reset_to_default(is_app_closing=True)
   
        if hasattr(self, 'autoclicker_controller') and self.autoclicker_controller and self.autoclicker_controller.is_active:
            self.autoclicker_controller.stop(is_app_closing=True)
            self.autoclicker_controller.reset_to_default(is_app_closing=True)
   
        if hasattr(self, 'streamprotect_controller') and self.streamprotect_controller and self.streamprotect_controller.initialized:
            if self.streamprotect_controller.is_active:
                self.streamprotect_controller.stop()
            self.streamprotect_controller.reset_to_default(is_app_closing=True)
   
        if hasattr(self, 'speed_controller') and self.speed_controller and self.speed_controller.initialized:
            if self.speed_controller.is_active:
                self.speed_controller.stop(is_app_closing=True)
            self.speed_controller.reset_to_default(is_app_closing=True)
   
        if hasattr(self, 'sprint_controller') and self.sprint_controller and self.sprint_controller.initialized:
            if self.sprint_controller.is_active:
                self.sprint_controller.stop(is_app_closing=True)
            self.sprint_controller.reset_to_default(is_app_closing=True)
        if hasattr(self, 'truesight_controller') and self.truesight_controller and self.truesight_controller.initialized:
            if self.truesight_controller.is_active:
                self.truesight_controller.stop(is_app_closing=True)
            self.truesight_controller.reset_to_default(is_app_closing=True)

        if hasattr(self, 'timechanger_controller') and self.timechanger_controller and self.timechanger_controller.initialized:
            if self.timechanger_controller.is_active:
                self.timechanger_controller.stop(is_app_closing=True)
            self.timechanger_controller.reset_to_default(is_app_closing=True)

        if self.minecraft_version == "1.21.13" and hasattr(self, 'nohurtcam_controller') and self.nohurtcam_controller and self.nohurtcam_controller.initialized:
            if self.nohurtcam_controller.is_active:
                self.nohurtcam_controller.stop(is_app_closing=True)
            self.nohurtcam_controller.reset_to_default(is_app_closing=True)
   
        try:
            self.attributes('-topmost', False)
            if hasattr(self, 'keybind_window') and self.keybind_window and self.keybind_window.winfo_exists():
                self.keybind_window.attributes('-topmost', False)
        except:
            pass
        self.destroy()
if __name__ == "__main__":
    app = MinecraftModApp()

    app.mainloop()
