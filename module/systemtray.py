import pystray
import threading
import time
import ctypes
from PIL import Image
import os
import sys

class SystemTrayController:
    def __init__(self, app):
        self.app = app
        self.icon = None
        self.is_active = False
        self.initialized = False
        self.thread = None
        self.update_queue = None
        self._stop_flag = False
        self._has_printed_init = False

    def set_update_queue(self, queue):
        self.update_queue = queue

    def resource_path(self, relative_path):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def _create_image(self):
        path = self.resource_path("icons/icon.png")
        img = Image.open(path)
        img = img.resize((32, 32), Image.Resampling.LANCZOS)
        return img.convert('RGB')

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(
                "Show Torio Client",
                self.show_window,
                default=True
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Exit",
                self.exit_app
            )
        )

    def start(self):
        if self.is_active:
            return True
        try:
            self._stop_flag = False
            image = self._create_image()
            menu = self._build_menu()
            self.icon = pystray.Icon(
                "TorioClient",
                image,
                "Torio Client",
                menu
            )
            self.thread = threading.Thread(target=self._run_icon, daemon=True)
            self.thread.start()
            time.sleep(0.1)
            self.is_active = True
            self.initialized = True
            if self.update_queue:
                self.update_queue.put(('status_update', ('systemtray', "Active", '#00e676')))
            if not self._has_printed_init:
                print("SystemTray: initialized")
                self._has_printed_init = True
            return True
        except Exception:
            self.is_active = False
            if self.update_queue:
                self.update_queue.put(('status_update', ('systemtray', "Failed to create tray", '#ff5252')))
            return False

    def _run_icon(self):
        try:
            self.icon.run()
        except Exception:
            self.is_active = False

    def stop(self):
        if not self.is_active:
            return True
        try:
            self._stop_flag = True
            if self.icon:
                self.icon.stop()
                self.icon = None
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=1.0)
            self.is_active = False
            if self.update_queue:
                self.update_queue.put(('status_update', ('systemtray', "Inactive", '#a0a0b0')))
            return True
        except Exception:
            return False

    def show_window(self, icon=None, item=None):
        try:
            self.app.after(0, self._force_focus)
        except Exception:
            pass

    def _force_focus(self):
        try:
            if self.app.state() == "iconic" or self.app.state() == "withdrawn":
                self.app.deiconify()
            self.app.focus_force()
            self.app.lift()
            self.app.attributes('-topmost', True)
            self.app.after(100, lambda: self._restore_topmost())
            
        except Exception:
            pass

    def _restore_topmost(self):
        try:
            if hasattr(self.app, 'streamprotect_controller'):
                if self.app.streamprotect_controller.is_active:
                    return
            
            self.app.attributes('-topmost', False)
        except Exception:
            pass

    def exit_app(self, icon=None, item=None):
        try:
            if self.is_active:
                self.stop()
            self.app.after(0, self.app.on_closing)
            
        except Exception:
            pass

    def reset_to_default(self, is_app_closing=False):
        if self.is_active:
            self.stop()
        
        self.is_active = False
        self.initialized = False
        self.icon = None
        self.thread = None
        self._stop_flag = False