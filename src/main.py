import threading
import tkinter as tk
from tkinter import ttk
from ui import (
    create_ui,
    update_status,
    update_progress,
    update_total_files,
    update_current_file,
    enable_backup_button,
    format_elapsed_time  # Add to imports
)
from scraper import FileScraper
import time
import json
import os
import winreg
import fnmatch  # Add this import at the top with other imports.

# Declare global storage (optional)
INDEXED_FILES = []
INDEXED_FOLDERS = []

def safe_update_status(root: tk.Tk, status_label: tk.Label, message: str) -> None:
    root.after(0, lambda: update_status(status_label, message))

def safe_update_progress(root: tk.Tk, progress: ttk.Progressbar, value: int) -> None:
    root.after(0, lambda: update_progress(progress, value))

def is_ignored_file(file_path: str, file_type: str) -> bool:
    """Return True if the file should be ignored based on its path."""
    ignore_dirs = [
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\ProgramData",
        "C:\\$Recycle.Bin",
        "C:\\msys64",
        "C:\\vcpkg"
    ]
    file_path_lower = file_path.lower()
    for ignore in ignore_dirs:
        if file_path.startswith(ignore):
            return True
    if "appdata" in file_path_lower or "$recycle.bin" in file_path_lower:
        return True
    return False

def get_user_directories() -> list[str]:
    """Return a list of user directories from the registry."""
    user_dirs = []
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList")
        num_subkeys = winreg.QueryInfoKey(key)[0]
        for i in range(num_subkeys):
            subkey_name = winreg.EnumKey(key, i)
            subkey = winreg.OpenKey(key, subkey_name)
            try:
                profile_path, _ = winreg.QueryValueEx(subkey, "ProfileImagePath")
                if profile_path.lower().startswith("c:\\users") and os.path.isdir(profile_path):
                    user_dirs.append(profile_path)
            except FileNotFoundError:
                continue
        winreg.CloseKey(key)
    except Exception:
        pass
    return user_dirs

def run_scraper(
    scraper: FileScraper,
    root: tk.Tk,
    progress: ttk.Progressbar,
    status_label: tk.Label,
    total_files_label: tk.Label,
    current_file_label: tk.Label,
    settings: dict,
    scan_mode: str,  # e.g., "text", "image", "video", or "full"
    backup_btn: tk.Button
) -> None:
    start_time = time.time()
    safe_update_status(root, status_label, "Preparing scan directories...")
    user_dirs = []
    # Get all available user directories from registry.
    all_users = {}  # mapping: username -> path
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList")
        num_subkeys = winreg.QueryInfoKey(key)[0]
        for i in range(num_subkeys):
            subkey_name = winreg.EnumKey(key, i)
            subkey = winreg.OpenKey(key, subkey_name)
            try:
                profile_path, _ = winreg.QueryValueEx(subkey, "ProfileImagePath")
                if profile_path.lower().startswith("c:\\users") and os.path.isdir(profile_path):
                    user_name = os.path.basename(profile_path)
                    all_users[user_name] = profile_path
            except FileNotFoundError:
                continue
        winreg.CloseKey(key)
    except Exception:
        pass
    # If settings have user_accounts, use them; otherwise, default to all available users.
    if "user_accounts" in settings and settings["user_accounts"]:
        for user, var in settings["user_accounts"].items():
            if var.get() and user in all_users:
                user_dirs.append(all_users[user])
    else:
        user_dirs = list(all_users.values())
    
    # Optionally add additional directories if needed.
    if os.path.isdir("C:\\arche"):
        user_dirs.append("C:\\arche")
    
    all_files = FileScraper().scan_all_files(user_dirs)
    safe_update_progress(root, progress, 25)
    
    # Filter files based on scan_mode.
    if scan_mode == "text":
        files_to_scan = [f for f in all_files if f.lower().endswith('.txt') or f.lower().endswith('.asc')]
    elif scan_mode == "image":
        files_to_scan = [f for f in all_files if any(f.lower().endswith(ext) for ext in ['.png','.jpg','.jpeg','.gif'])]
    elif scan_mode == "video":
        files_to_scan = [f for f in all_files if any(f.lower().endswith(ext) for ext in ['.mp4','.avi','.mkv'])]
    else:  # full scan
        desired_extensions = ['.txt', '.asc', '.png','.jpg','.jpeg','.gif', '.mp4','.avi','.mkv', '.mp3']  # add any extensions as needed
        files_to_scan = [f for f in all_files if f.endswith(tuple(desired_extensions))]

    safe_update_status(root, status_label, f"Found {len(files_to_scan)} files for {scan_mode} scan.")
    safe_update_progress(root, progress, 50)
    
    # Helper to check if file path has a hidden folder (folder name starting with '.')
    def has_dot_folder(file_path: str) -> bool:
        parts = os.path.normpath(file_path).split(os.path.sep)
        # Skip drive letter component for Windows.
        for part in parts[1:]:
            if part.startswith('.') and part != '.':
                return True
        return False
    
    # Helper: check if file path contains any folder matching a skip pattern.
    def has_skip_folder(file_path: str, skip_patterns: list[str]) -> bool:
        parts = os.path.normpath(file_path).split(os.path.sep)
        for part in parts[1:]:
            for pattern in skip_patterns:
                if pattern and pattern.lower() in part.lower():
                    return True
        return False

    def is_downloads(file_path: str) -> bool:
        normalized = os.path.normpath(file_path).lower()
        return os.path.sep + "downloads" + os.path.sep in normalized
    
    # Retrieve skip patterns from settings (assumes a list).
    skip_patterns = settings.get("skip_folders", [])
    
    filtered_files = []
    for f in files_to_scan:
        if is_ignored_file(f, scan_mode):
            continue
        if settings.get("ignore_downloads", tk.BooleanVar()).get() and is_downloads(f):
            continue
        # Use fnmatch for each folder in the file path to support wildcards (e.g., ".*").
        parts = os.path.normpath(f).split(os.path.sep)
        if skip_patterns and any(fnmatch.fnmatchcase(part.lower(), pattern.lower()) for part in parts[1:] for pattern in skip_patterns if pattern):
            continue
        filtered_files.append({"path": f, "name": os.path.basename(f), "type": scan_mode})
    
    with open("results.json", "w", encoding="utf-8") as json_file:
        json.dump(filtered_files, json_file, indent=2)
    
    elapsed = time.time() - start_time
    safe_update_status(root, status_label, 
                      f"{scan_mode.capitalize()} scan complete! ({format_elapsed_time(elapsed)})\n"
                      f"Results logged to results.json")
    safe_update_progress(root, progress, 100)
    
    # Enable backup button with found files
    root.after(0, lambda: enable_backup_button(backup_btn, filtered_files))

def main() -> None:
    # Create the UI (now returns backup button as well)
    (root, progress, status_label, total_files_label, current_file_label,
     settings, btn_text, btn_image, btn_video, btn_full, backup_btn) = create_ui()
    scraper = FileScraper()
    
    # New: initial indexing of files (do nothing with them except store folder info)
    def initial_index():
        # Build user directories similarly to run_scraper:
        user_dirs = []
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList")
            num_subkeys = winreg.QueryInfoKey(key)[0]
            for i in range(num_subkeys):
                subkey_name = winreg.EnumKey(key, i)
                subkey = winreg.OpenKey(key, subkey_name)
                try:
                    profile_path, _ = winreg.QueryValueEx(subkey, "ProfileImagePath")
                    if profile_path.lower().startswith("c:\\users") and os.path.isdir(profile_path):
                        user_dirs.append(profile_path)
                except FileNotFoundError:
                    continue
            winreg.CloseKey(key)
        except Exception:
            pass
        if os.path.isdir("C:\\arche"):
            user_dirs.append("C:\\arche")
        files = scraper.scan_all_files(user_dirs)
        global INDEXED_FILES, INDEXED_FOLDERS
        INDEXED_FILES = files
        INDEXED_FOLDERS = sorted({os.path.dirname(f) for f in files})
        # Store indexed folders in settings for use in the block window.
        settings["indexed_folders"] = INDEXED_FOLDERS
        safe_update_status(root, status_label, f"Initial indexing complete: {len(INDEXED_FOLDERS)} folders found.")
    threading.Thread(target=initial_index, daemon=True).start()
    
    def start_scan(mode: str):
        threading.Thread(
            target=run_scraper,
            args=(scraper, root, progress, status_label, total_files_label, current_file_label, settings, mode, backup_btn),
            daemon=True
        ).start()
    
    # Bind button commands.
    btn_text.config(command=lambda: start_scan("text"))
    btn_image.config(command=lambda: start_scan("image"))
    btn_video.config(command=lambda: start_scan("video"))
    btn_full.config(command=lambda: start_scan("full"))
    
    # Remove auto-start of full scan.
    
    root.mainloop()

if __name__ == "__main__":
    main()
