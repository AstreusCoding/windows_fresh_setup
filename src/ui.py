import os
import tkinter as tk
from tkinter import ttk
import json
import fnmatch
from tkinter import filedialog, messagebox
import shutil
from datetime import datetime
import time  # Add to imports if not present

def open_settings_menu(root: tk.Tk, settings: dict) -> None:
    """Open a settings window with user account toggles and ignore downloads option."""
    settings_win = tk.Toplevel(root)
    settings_win.title("Settings")
    settings_win.geometry("300x400")
    
    tk.Label(settings_win, text="Select User Accounts to Scan:").pack(pady=5)
    user_frame = tk.Frame(settings_win)
    user_frame.pack(fill="both", expand=True)
    
    # Populate user_accounts only if not already set.
    if "user_accounts" not in settings:
        ignore_users = {"public", "default", "default user", "all users"}
        user_dirs = []
        try:
            for entry in os.listdir("C:\\Users"):
                if entry.lower() not in ignore_users:
                    user_dirs.append(entry)
        except Exception:
            pass
        settings["user_accounts"] = {}
        for user in sorted(user_dirs):
            var = tk.BooleanVar(value=True)
            chk = tk.Checkbutton(user_frame, text=user, variable=var)
            chk.pack(anchor="w", padx=10, pady=2)
            settings["user_accounts"][user] = var
    else:
        # If already set, recreate checkbuttons with existing variables.
        for user, var in settings["user_accounts"].items():
            chk = tk.Checkbutton(user_frame, text=user, variable=var)
            chk.pack(anchor="w", padx=10, pady=2)
    
    tk.Label(settings_win, text="Folder names to skip:").pack(pady=5)
    # Initialize skip_folders as a list if not set.
    if "skip_folders" not in settings:
        settings["skip_folders"] = []
    # Frame for input and listbox.
    skip_frame = tk.Frame(settings_win)
    skip_frame.pack(padx=10, pady=5, fill="x")
    # Entry for new folder pattern.
    new_skip_var = tk.StringVar()
    skip_entry = tk.Entry(skip_frame, textvariable=new_skip_var)
    skip_entry.grid(row=0, column=0, sticky="ew")
    skip_frame.columnconfigure(0, weight=1)
    # Button to add pattern.
    def add_skip():
        pattern = new_skip_var.get().strip()
        if pattern and pattern not in settings["skip_folders"]:
            settings["skip_folders"].append(pattern)
            skip_listbox.insert(tk.END, pattern)
            new_skip_var.set("")
    tk.Button(skip_frame, text="Add", command=add_skip).grid(row=0, column=1, padx=5)
    # Listbox showing current skip patterns.
    skip_listbox = tk.Listbox(skip_frame, height=4)
    skip_listbox.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
    # Populate listbox with existing patterns.
    for pattern in settings["skip_folders"]:
        skip_listbox.insert(tk.END, pattern)
    # Button to remove selected pattern.
    def remove_skip():
        sel = list(skip_listbox.curselection())
        if sel:
            for index in sorted(sel, reverse=True):
                del settings["skip_folders"][index]
            # Refresh the listbox.
            skip_listbox.delete(0, tk.END)
            for pattern in settings["skip_folders"]:
                skip_listbox.insert(tk.END, pattern)
    tk.Button(skip_frame, text="Remove Selected", command=remove_skip).grid(row=2, column=0, columnspan=2, pady=5)
    
    # New button: Block folders based off an initial search.
    tk.Button(settings_win, text="Block Folders from Search", command=lambda: open_block_folders_window(root, settings)).pack(pady=5)
    # New button: Save settings to JSON.
    tk.Button(settings_win, text="Save Settings", command=lambda: save_settings(settings)).pack(pady=5)
    
    tk.Button(settings_win, text="Close", command=settings_win.destroy).pack(pady=10)

def open_block_folders_window(root: tk.Tk, settings: dict) -> None:
    block_win = tk.Toplevel(root)
    block_win.title("Block Folders from Search")
    block_win.geometry("350x300")
    tk.Label(block_win, text="Select folder(s) to block:").pack(pady=5)
    folders_listbox = tk.Listbox(block_win, selectmode=tk.MULTIPLE, height=10)
    folders_listbox.pack(padx=10, pady=5, fill="both", expand=True)
    # Updated helper: check each component of candidate's path for wildcard match.
    def is_subblocked(candidate: str, blocked_list: list[str]) -> bool:
        candidate_abs = os.path.abspath(candidate)
        # Check absolute patterns.
        for b in blocked_list:
            if os.path.isabs(b):
                try:
                    b_abs = os.path.abspath(b)
                    if candidate_abs == b_abs or candidate_abs.startswith(b_abs + os.path.sep):
                        return True
                except Exception:
                    pass
            else:
                # Check each directory component.
                parts = os.path.normpath(candidate_abs).split(os.path.sep)
                for part in parts:
                    if fnmatch.fnmatchcase(part, b):
                        return True
        return False
    # Retrieve indexed folders and currently blocked folders.
    indexed = settings.get("indexed_folders", [])
    blocked = settings.get("skip_folders", [])
    filtered_folders = [f for f in indexed if not is_subblocked(f, blocked)]
    # Replace synchronous population with lazy batch loading.
    filtered_iter = iter(sorted(filtered_folders))
    batch_size = 50
    def load_batch():
        count = 0
        for folder in filtered_iter:
            folders_listbox.insert(tk.END, folder)
            count += 1
            if count >= batch_size:
                block_win.after(10, load_batch)
                return
    load_batch()
    def block_selected():
        sel = folders_listbox.curselection()
        for idx in sel:
            folder = folders_listbox.get(idx)
            if folder not in settings.get("skip_folders", []):
                settings["skip_folders"].append(folder)
        block_win.destroy()
    tk.Button(block_win, text="Block Selected", command=block_selected).pack(pady=5)

def load_settings() -> dict:
    if os.path.exists("settings.json"):
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            # Convert plain types back into our settings structure.
            result = {}
            result["ignore_downloads"] = tk.BooleanVar(value=data.get("ignore_downloads", False))
            result["skip_folders"] = data.get("skip_folders", [])
            # user_accounts will be set later by open_settings_menu.
            return result
        except Exception:
            return {}
    return {}

def save_settings(settings: dict) -> None:
    # Prepare plain settings; convert tk.BooleanVar to bool.
    plain = {}
    if "ignore_downloads" in settings:
        plain["ignore_downloads"] = settings["ignore_downloads"].get()
    plain["skip_folders"] = settings.get("skip_folders", [])
    with open("settings.json", "w", encoding="utf-8") as f:
        json.dump(plain, f, indent=2)

def backup_files(root: tk.Tk, files_to_backup: list[dict]) -> None:
    """Create a backup of the found files."""
    if not files_to_backup:
        messagebox.showwarning("No Files", "No files available to backup.")
        return
    
    # Ask user for backup style
    style_win = tk.Toplevel(root)
    style_win.title("Backup Style")
    style_win.geometry("300x150")
    
    use_categories = tk.BooleanVar(value=True)
    tk.Checkbutton(
        style_win, 
        text="Sort files into categories (images, videos, text files)", 
        variable=use_categories
    ).pack(pady=10)
    
    def start_backup():
        style_win.destroy()
        perform_backup(root, files_to_backup, use_categories.get())
    
    tk.Button(style_win, text="Start Backup", command=start_backup).pack(pady=10)
    
def format_elapsed_time(seconds: float) -> str:
    """Format elapsed time in seconds to a human readable string."""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    minutes = int(seconds / 60)
    seconds = seconds % 60
    if minutes < 60:
        return f"{minutes}m {seconds:.1f}s"
    hours = int(minutes / 60)
    minutes = minutes % 60
    return f"{hours}h {minutes}m {seconds:.1f}s"

def perform_backup(root: tk.Tk, files_to_backup: list[dict], use_categories: bool) -> None:
    """Perform the actual backup operation."""
    start_time = time.time()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backups", f"backup_{timestamp}")
    
    try:
        os.makedirs(backup_dir, exist_ok=True)
    except Exception as e:
        messagebox.showerror("Error", f"Could not create backup directory: {e}")
        return
    
    progress_win = tk.Toplevel(root)
    progress_win.title("Backup Progress")
    progress_win.geometry("300x200")  # Made taller for elapsed time
    
    progress = ttk.Progressbar(progress_win, orient="horizontal", length=250, mode="determinate")
    progress.pack(pady=20)
    status_label = tk.Label(progress_win, text="Preparing backup...")
    status_label.pack(pady=5)
    time_label = tk.Label(progress_win, text="Elapsed: 0s")
    time_label.pack(pady=5)
    
    def update_elapsed():
        if progress_win.winfo_exists():
            elapsed = time.time() - start_time
            time_label.config(text=f"Elapsed: {format_elapsed_time(elapsed)}")
            progress_win.after(1000, update_elapsed)
    
    update_elapsed()
    
    total_files = len(files_to_backup)
    copied = 0
    
    for file_info in files_to_backup:
        try:
            src_path = file_info["path"]
            if use_categories:
                # Determine category based on file extension for full scans
                file_lower = src_path.lower()
                if file_info["type"] == "full":
                    if file_lower.endswith(('.txt', '.asc')):
                        category_dir = "text_files"
                    elif file_lower.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        category_dir = "images"
                    elif file_lower.endswith(('.mp4', '.avi', '.mkv')):
                        category_dir = "videos"
                    elif file_lower.endswith('.mp3'):
                        category_dir = "music"
                    else:
                        category_dir = "other"
                else:
                    # For specific scans, use the scan type
                    category_dir = {
                        "text": "text_files",
                        "image": "images",
                        "video": "videos"
                    }.get(file_info["type"], "other")
                
                dst_path = os.path.join(backup_dir, category_dir, os.path.basename(src_path))
            else:
                # Preserve original structure
                rel_path = os.path.splitdrive(src_path)[1].lstrip(os.sep)
                dst_path = os.path.join(backup_dir, rel_path)
            
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.copy2(src_path, dst_path)
            
            copied += 1
            progress['value'] = (copied / total_files) * 100
            status_label.config(text=f"Copying: {copied}/{total_files}")
            progress_win.update()
            
        except Exception as e:
            print(f"Error copying {src_path}: {e}")
    
    elapsed = time.time() - start_time
    progress_win.destroy()
    messagebox.showinfo("Backup Complete", 
                       f"Successfully backed up {copied} files to {backup_dir}\n"
                       f"Time taken: {format_elapsed_time(elapsed)}")

def create_ui() -> tuple[tk.Tk, ttk.Progressbar, tk.Label, tk.Label, tk.Label, dict, tk.Button, tk.Button, tk.Button, tk.Button, tk.Button]:
    """
    Create and return the main UI including:
    - Progress bar, status, total files, current file labels.
    - Scan buttons for text, images, videos, full scan.
    - A settings button (data returned in a settings dictionary).
    Returns:
      root, progress, status_label, total_files_label, current_file_label,
      settings, btn_text, btn_image, btn_video, btn_full, backup_btn.
    """
    root = tk.Tk()
    root.title("File Scraper")
    root.geometry("500x400")
    root.resizable(False, False)
    
    # Progress bar and status labels.
    progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
    progress.pack(pady=10)
    status_label = tk.Label(root, text="Status: Ready")
    status_label.pack(pady=5)
    total_files_label = tk.Label(root, text="Total files found: 0")
    total_files_label.pack(pady=5)
    current_file_label = tk.Label(root, text="Current file: None")
    current_file_label.pack(pady=5)
    
    # Frame for scan buttons.
    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=15)
    btn_text = tk.Button(btn_frame, text="Scan Text Files", width=15)
    btn_text.grid(row=0, column=0, padx=5, pady=5)
    btn_image = tk.Button(btn_frame, text="Scan Image Files", width=15)
    btn_image.grid(row=0, column=1, padx=5, pady=5)
    btn_video = tk.Button(btn_frame, text="Scan Video Files", width=15)
    btn_video.grid(row=1, column=0, padx=5, pady=5)
    btn_full = tk.Button(btn_frame, text="Full Scan", width=15)
    btn_full.grid(row=1, column=1, padx=5, pady=5)
    
    # Settings button.
    settings = load_settings()
    tk.Button(root, text="Settings", command=lambda: open_settings_menu(root, settings)).pack(pady=10)
    
    # Add backup button (initially disabled)
    backup_btn = tk.Button(root, text="Backup Files", state="disabled")
    backup_btn.pack(pady=5)
    
    return root, progress, status_label, total_files_label, current_file_label, settings, btn_text, btn_image, btn_video, btn_full, backup_btn

def enable_backup_button(backup_btn: tk.Button, files: list[dict]) -> None:
    """Enable the backup button and configure it with the files to backup."""
    backup_btn.config(
        state="normal",
        command=lambda: backup_files(backup_btn.master, files)
    )

def update_total_files(total_files_label: tk.Label, count: int) -> None:
    """Update the total files found label."""
    total_files_label.config(text=f"Total files found: {count}")

def update_current_file(current_file_label: tk.Label, file_name: str) -> None:
    """Update the current file being processed label."""
    current_file_label.config(text=f"Current file: {file_name}")

def update_status(status_label: tk.Label, message: str) -> None:
    """Update the status label with a new message."""
    status_label.config(text=message)

def update_progress(progress: ttk.Progressbar, value: int) -> None:
    """Update the progress bar value."""
    progress['value'] = value
