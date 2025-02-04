import threading
import tkinter as tk
from tkinter import ttk
import time
import json
import os
import winreg
import fnmatch

from ui import (
    create_ui,
    update_status,
    update_progress,
    update_total_files,
    update_current_file,
    enable_backup_button,
    format_elapsed_time  # Added to imports
)
from scraper import FileScraper

# Global storage for indexed files and folders.
INDEXED_FILES = []
INDEXED_FOLDERS = []


def safe_update_status(root: tk.Tk, status_label: tk.Label, message: str) -> None:
    """
    Safely update the status label in the UI using the main thread.
    
    Parameters:
        root: The main Tkinter window.
        status_label: The label widget to update.
        message: The message to display.
    """
    root.after(0, lambda: update_status(status_label, message))


def safe_update_progress(root: tk.Tk, progress: ttk.Progressbar, value: int) -> None:
    """
    Safely update the progress bar value in the UI using the main thread.
    
    Parameters:
        root: The main Tkinter window.
        progress: The progress bar widget.
        value: The progress value (0-100).
    """
    root.after(0, lambda: update_progress(progress, value))


def is_ignored_file(file_path: str, file_type: str) -> bool:
    """
    Determine whether a file should be ignored based on its path.
    
    Parameters:
        file_path: The full path of the file.
        file_type: The type of scan (e.g., 'text', 'image', 'video', etc.).
    
    Returns:
        True if the file should be ignored, False otherwise.
    """
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


def get_all_user_profiles() -> dict[str, str]:
    """
    Retrieve all user profiles from the Windows registry.
    
    Returns:
        A dictionary mapping usernames to their profile paths.
    """
    all_users = {}
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"
        )
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
    return all_users


def get_all_user_directories() -> list[str]:
    """
    Retrieve user directories from the registry without filtering by account.
    
    Returns:
        A list of user directory paths.
    """
    user_dirs = []
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"
        )
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


def get_files_by_scan_mode(all_files: list[str], scan_mode: str) -> list[str]:
    """
    Filter a list of files based on the specified scan mode.
    
    Parameters:
        all_files: List of file paths.
        scan_mode: One of "text", "image", "video", or "full".
    
    Returns:
        A list of file paths that match the scan mode criteria.
    """
    if scan_mode == "text":
        return [f for f in all_files if f.lower().endswith('.txt') or f.lower().endswith('.asc')]
    elif scan_mode == "image":
        return [f for f in all_files if any(f.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif'])]
    elif scan_mode == "video":
        return [f for f in all_files if any(f.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mkv'])]
    else:  # full scan
        desired_extensions = ['.txt', '.asc', '.png', '.jpg', '.jpeg', '.gif', '.mp4', '.avi', '.mkv', '.mp3']
        return [f for f in all_files if f.endswith(tuple(desired_extensions))]


def is_downloads(file_path: str) -> bool:
    """
    Check if the file is located in a downloads directory.
    
    Parameters:
        file_path: The full file path.
    
    Returns:
        True if the file is in a downloads directory, False otherwise.
    """
    normalized = os.path.normpath(file_path).lower()
    return os.path.sep + "downloads" + os.path.sep in normalized


def has_skip_folder(file_path: str, skip_patterns: list[str]) -> bool:
    """
    Check if any folder in the file path matches a skip pattern.
    
    Parameters:
        file_path: The full file path.
        skip_patterns: A list of folder patterns to skip.
    
    Returns:
        True if any folder in the path matches a skip pattern, False otherwise.
    """
    parts = os.path.normpath(file_path).split(os.path.sep)
    return any(
        fnmatch.fnmatchcase(part.lower(), pattern.lower())
        for part in parts[1:]
        for pattern in skip_patterns if pattern
    )


def apply_additional_filters(files: list[str], scan_mode: str, settings: dict) -> list[dict]:
    """
    Apply additional filtering to the list of files based on settings.
    
    Parameters:
        files: List of file paths to filter.
        scan_mode: The scan mode used (e.g., 'text', 'image', 'video', or 'full').
        settings: A dictionary of settings that may include skip patterns and a downloads ignore flag.
    
    Returns:
        A list of dictionaries containing file information that passed the filters.
    """
    skip_patterns = settings.get("skip_folders", [])
    filtered_files = []
    for f in files:
        if is_ignored_file(f, scan_mode):
            continue
        # If the "ignore_downloads" setting is enabled.
        if settings.get("ignore_downloads", tk.BooleanVar()).get() and is_downloads(f):
            continue
        if skip_patterns and has_skip_folder(f, skip_patterns):
            continue
        filtered_files.append({
            "path": f,
            "name": os.path.basename(f),
            "type": scan_mode
        })
    return filtered_files


def save_results(results: list[dict], filename: str) -> None:
    """
    Save the scan results to a JSON file.
    
    Parameters:
        results: The list of file dictionaries.
        filename: The name of the file to save the results.
    """
    with open(filename, "w", encoding="utf-8") as json_file:
        json.dump(results, json_file, indent=2)


def run_scraper(
    scraper: FileScraper,
    root: tk.Tk,
    progress: ttk.Progressbar,
    status_label: tk.Label,
    total_files_label: tk.Label,
    current_file_label: tk.Label,
    settings: dict,
    scan_mode: str,
    backup_btn: tk.Button
) -> None:
    """
    Execute the file scanning process and update the UI accordingly.
    
    Parameters:
        scraper: An instance of FileScraper to perform the scanning.
        root: The main Tkinter window.
        progress: The progress bar widget.
        status_label: The label widget for status updates.
        total_files_label: Label for displaying the total file count (unused in current logic).
        current_file_label: Label for displaying the currently scanned file (unused in current logic).
        settings: Dictionary of settings from the UI.
        scan_mode: The mode of scan ("text", "image", "video", or "full").
        backup_btn: The backup button widget to enable after scanning.
    """
    start_time = time.time()
    safe_update_status(root, status_label, "Preparing scan directories...")

    # Retrieve user directories based on settings.
    all_users = get_all_user_profiles()
    user_dirs = []
    if "user_accounts" in settings and settings["user_accounts"]:
        for user, var in settings["user_accounts"].items():
            if var.get() and user in all_users:
                user_dirs.append(all_users[user])
    else:
        user_dirs = list(all_users.values())

    # Optionally add additional directories.
    if os.path.isdir("C:\\arche"):
        user_dirs.append("C:\\arche")

    all_files = scraper.scan_all_files(user_dirs)
    safe_update_progress(root, progress, 25)

    # Filter files based on scan mode.
    files_to_scan = get_files_by_scan_mode(all_files, scan_mode)
    safe_update_status(root, status_label, f"Found {len(files_to_scan)} files for {scan_mode} scan.")
    safe_update_progress(root, progress, 50)

    # Apply additional filters.
    filtered_files = apply_additional_filters(files_to_scan, scan_mode, settings)

    # Save results to a JSON file.
    save_results(filtered_files, "results.json")

    elapsed = time.time() - start_time
    safe_update_status(
        root,
        status_label,
        f"{scan_mode.capitalize()} scan complete! ({format_elapsed_time(elapsed)})\nResults logged to results.json"
    )
    safe_update_progress(root, progress, 100)

    # Enable backup button with the found files.
    root.after(0, lambda: enable_backup_button(backup_btn, filtered_files))


def initial_index(scraper: FileScraper, root: tk.Tk, status_label: tk.Label, settings: dict) -> None:
    """
    Perform initial indexing of files to prepare folder information for later use.
    
    Parameters:
        scraper: An instance of FileScraper to perform the indexing.
        root: The main Tkinter window.
        status_label: The label widget for status updates.
        settings: Dictionary of settings from the UI.
    """
    user_dirs = get_all_user_directories()
    if os.path.isdir("C:\\arche"):
        user_dirs.append("C:\\arche")
    files = scraper.scan_all_files(user_dirs)
    global INDEXED_FILES, INDEXED_FOLDERS
    INDEXED_FILES = files
    INDEXED_FOLDERS = sorted({os.path.dirname(f) for f in files})
    # Store indexed folders in settings for use elsewhere.
    settings["indexed_folders"] = INDEXED_FOLDERS
    safe_update_status(root, status_label, f"Initial indexing complete: {len(INDEXED_FOLDERS)} folders found.")


def start_scan_thread(
    scraper: FileScraper,
    root: tk.Tk,
    progress: ttk.Progressbar,
    status_label: tk.Label,
    total_files_label: tk.Label,
    current_file_label: tk.Label,
    settings: dict,
    scan_mode: str,
    backup_btn: tk.Button
) -> None:
    """
    Start a new thread to run the scraper for the given scan mode.
    
    Parameters:
        scraper: An instance of FileScraper.
        root: The main Tkinter window.
        progress: The progress bar widget.
        status_label: The label widget for status updates.
        total_files_label: Label for total files (unused).
        current_file_label: Label for current file (unused).
        settings: Dictionary of settings from the UI.
        scan_mode: The scan mode to execute.
        backup_btn: The backup button widget to enable after scanning.
    """
    threading.Thread(
        target=run_scraper,
        args=(
            scraper,
            root,
            progress,
            status_label,
            total_files_label,
            current_file_label,
            settings,
            scan_mode,
            backup_btn
        ),
        daemon=True
    ).start()


def main() -> None:
    """
    Initialize the UI and start the application.
    """
    # Create the UI components.
    (root, progress, status_label, total_files_label, current_file_label,
     settings, btn_text, btn_image, btn_video, btn_full, backup_btn) = create_ui()
    scraper = FileScraper()

    # Start initial indexing in a separate thread.
    threading.Thread(
        target=initial_index,
        args=(scraper, root, status_label, settings),
        daemon=True
    ).start()

    # Bind button commands to start scans.
    btn_text.config(
        command=lambda: start_scan_thread(
            scraper, root, progress, status_label, total_files_label,
            current_file_label, settings, "text", backup_btn
        )
    )
    btn_image.config(
        command=lambda: start_scan_thread(
            scraper, root, progress, status_label, total_files_label,
            current_file_label, settings, "image", backup_btn
        )
    )
    btn_video.config(
        command=lambda: start_scan_thread(
            scraper, root, progress, status_label, total_files_label,
            current_file_label, settings, "video", backup_btn
        )
    )
    btn_full.config(
        command=lambda: start_scan_thread(
            scraper, root, progress, status_label, total_files_label,
            current_file_label, settings, "full", backup_btn
        )
    )

    root.mainloop()


if __name__ == "__main__":
    main()
