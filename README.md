# Torio Ghost Client
**Torio Ghost Client source code**

A custom Minecraft Bedrock Edition Client (Ghost Client) with various features.

**↓↓This page contains pre-built exe files:↓↓**

https://github.com/Uncle-Awrt/Torio-Client

## License
This project is licensed under the **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**.

- Give appropriate credit to **kukentyan** (e.g., "Created by kukentyan" with a link to this repository and the license).
- **NonCommercial**: You may not use the material for commercial purposes (no selling, no monetization, no profit-making activities).
- You are free to share (copy/redistribute) and adapt (modify/remix) the material, as long as you follow the above terms and indicate changes.

No other restrictions apply. Full legal text: [LICENSE](LICENSE)  
Official details: https://creativecommons.org/licenses/by-nc/4.0/

## Features
- Anti Knockback
- Reach
- Hitbox
- Zoom
- Brightness
- Speed
- Coordinates
- Auto Clicker
- Sprint
- No Hurt Cam
- True Sight
- Time Changer
- Stream Protection
- Fast Item
- SystemTray

## Requirements
- **Python 3.10+** (recommended: 3.11 or 3.12)
- Windows OS (tested on Windows 10/11)
- Minecraft Bedrock Edition (GDK: 1.21.120 ～ 1.21.132)

## Installation & Build Guide

### 1. Clone the Repository
```bash
git clone https://github.com/kukentyan/torio-master.git
cd torio-master
```

###2. Install Dependencies
```bash
pip install -r requirements.txt
```
(If you don't have requirements.txt yet, install these manually:)
```bash
pip install customtkinter pillow pygetwindow psutil pywin32 keyboard pynput pystray pymem
```
### 3. Build the Executable (.exe) with PyInstaller
From the project root directory, run this command to create a single-file executable:
```bash
pyinstaller --onefile --windowed --icon=icons/icon.ico --name=GhostClient --add-data "icons;icons" --add-data "config.json;."  --add-data "module/*.pyd;module" --add-data "icons/icon.png;icons" --hidden-import=customtkinter --hidden-import=pystray --hidden-import=pystray.menu --hidden-import=pystray._base --hidden-import=pystray._win32 --hidden-import=pystray._util --hidden-import=pystray._util.win32 --hidden-import=pywin32 --hidden-import=win32api --hidden-import=win32api --hidden-import=pywintypes --hidden-import=win32ctypes --hidden-import=win32gui --hidden-import=win32process --hidden-import=tkinter.messagebox --hidden-import=PIL --hidden-import=pygetwindow --hidden-import=PIL._tkinter_finder --hidden-import=pymem --hidden-import=keyboard --hidden-import=pynput --hidden-import=pynput.keyboard --hidden-import=pynput.mouse --hidden-import=tkinter --hidden-import=turtle --hidden-import=module.antiknockback --hidden-import=module.reach --hidden-import=module.hitbox --hidden-import=module.zoom --hidden-import=module.brightness --hidden-import=module.speed --hidden-import=module.coordinates --hidden-import=module.autoclicker --hidden-import=module.sprint --hidden-import=module.nohurtcam --hidden-import=module.truesight --hidden-import=module.timechanger --hidden-import=module.streamprotect --hidden-import=module.fastitem --hidden-import=module.systemtray main.py
```
**Notes:**
After building, the standalone executable will be in the dist/ folder:
dist/GhostClient.exe
### 4. Run the Client
Double-click dist/GhostClient.exe
(or run python main.py for development/testing)

