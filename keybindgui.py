import customtkinter as ctk
from config import ConfigManager
import sys
import os

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

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

class ModernButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        default_kwargs = {
            "corner_radius": 8,
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
            "corner_radius": 10,
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

class ModernEntry(ctk.CTkEntry):
    def __init__(self, master, **kwargs):
        default_kwargs = {
            "corner_radius": 6,
            "border_width": 2,
            "border_color": COLORS["border"],
            "fg_color": COLORS["card"],
            "text_color": COLORS["text"],
            "font": ("Segoe UI", 12),
            "height": 32,
        }
        default_kwargs.update(kwargs)
        super().__init__(master, **default_kwargs)

class KeybindWindow(ctk.CTkToplevel):
    def __init__(self, parent, config: ConfigManager, update_callback=None):
        super().__init__(parent)
        icon_path = resource_path("icons/icon.ico")
        try:
            self.wm_iconbitmap(icon_path)
        except Exception as e:
            print(f"Failed to set window icon using wm_iconbitmap: {e}")

        self.config = config
        self.update_callback = update_callback
        self.keybind_entries = {}

        self.title("Keybind Settings")
        self.geometry("420x480")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["background"])
        
        self.transient(parent)
        self.grab_set()
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["surface"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"]
        )
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        keybind_features = {
            "brightness": "Fullbright",
            "zoom": "Zoom",
            "sprint": "Sprint",
            "autoclicker_left": "AutoClicker (Left)",
            "autoclicker_right": "AutoClicker (Right)",
        }
        
        for feature_key, feature_name in keybind_features.items():
            self.create_keybind_card(main_frame, feature_key, feature_name)
        
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        ModernButton(
            button_frame,
            text="Close",
            command=self.close_window
        ).pack(side="right", fill="x", expand=True)
    
    def create_keybind_card(self, parent, feature_key, feature_name):
        card = ModernFrame(parent)
        card.pack(fill="x", pady=6)
        
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=12)
        content.grid_columnconfigure(1, weight=1)
        
        ModernLabel(
            content,
            text=feature_name,
            font=("Segoe UI", 13, "bold"),
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=(0, 20))
        
        current_key = self.config.get_keybind(feature_key) or "None"
        
        key_entry = ModernEntry(
            content,
            width=120,
            justify="center"
        )
        key_entry.grid(row=0, column=1, sticky="e")
        key_entry.insert(0, current_key.upper())
        key_entry.configure(state="readonly")
        
        def on_key_press(event):
            new_key = event.keysym.lower()
            
            ignore_keys = [
                "shift", "shift_l", "shift_r",
                "control", "control_l", "control_r",
                "alt", "alt_l", "alt_r",
                "caps_lock", "tab", "escape",
                "super_l", "super_r", "win_l", "win_r"
            ]
            
            if new_key in ignore_keys:
                self.show_error(key_entry, "Invalid Key!")
                return
            
            current_keybinds = self.config.config.get("keybinds", {})
            for other_feature, bound_key in current_keybinds.items():
                if other_feature != feature_key and bound_key == new_key:
                    self.show_error(key_entry, "Key in Use!")
                    return

            self.config.set_keybind(feature_key, new_key)
            key_entry.configure(state="normal")
            key_entry.delete(0, "end")
            key_entry.insert(0, new_key.upper())
            key_entry.configure(state="readonly")
            
            self.show_success(key_entry)
            
            if self.update_callback:
                self.update_callback()
        
        def on_click(event):
            key_entry.configure(border_color=COLORS["accent_light"])
        
        def on_focus_out(event):
            key_entry.configure(border_color=COLORS["border"])
        
        key_entry.bind("<KeyPress>", on_key_press)
        key_entry.bind("<Button-1>", on_click)
        key_entry.bind("<FocusOut>", on_focus_out)
        
        self.keybind_entries[feature_key] = key_entry
    
    def show_success(self, entry):
        entry.configure(border_color=COLORS["success"], text_color=COLORS["success"])
        self.after(600, lambda: entry.configure(
            border_color=COLORS["border"],
            text_color=COLORS["text"]
        ))
    
    def show_error(self, entry, message):
        original_text = entry.get()
        entry.configure(
            border_color="#ff5252",
            text_color="#ff5252",
            state="normal"
        )
        entry.delete(0, "end")
        entry.insert(0, message)
        entry.configure(state="readonly")
        
        self.after(1200, lambda: self.restore_entry(entry, original_text))
    
    def restore_entry(self, entry, original_text):
        entry.configure(
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            state="normal"
        )
        entry.delete(0, "end")
        entry.insert(0, original_text)
        entry.configure(state="readonly")
    
    
    def close_window(self):
        self.grab_release()
        self.destroy()