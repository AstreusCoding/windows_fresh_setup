import os
import fnmatch
from concurrent.futures import ThreadPoolExecutor, wait
import winreg
from typing import Callable, Optional
import threading
from queue import Queue, Empty

class FileScraper:
    def __init__(self):
        self.text_file_pattern = '*.txt'
        self.image_patterns = ['*.png', '*.jpg', '*.jpeg', '*.gif']
        self.video_patterns = ['*.mp4', '*.avi', '*.mkv']

    def find_files(
        self,
        pattern: str,
        paths: list[str],
        file_found_callback: Optional[Callable[[str], None]] = None
    ) -> list[str]:
        """Find files matching the pattern in the given paths concurrently.
        
        Improved: Uses a Queue with a pool of worker threads to process directories.
        """
        matches = []
        lock = threading.Lock()
        dir_queue = Queue()
        for p in paths:
            dir_queue.put(p)
        
        def worker():
            while True:
                try:
                    current_dir = dir_queue.get_nowait()
                except Empty:
                    break
                try:
                    for entry in os.scandir(current_dir):
                        if entry.is_file() and fnmatch.fnmatch(entry.name, pattern):
                            with lock:
                                matches.append(entry.path)
                            if file_found_callback:
                                file_found_callback(entry.path)
                        elif entry.is_dir():
                            dir_queue.put(entry.path)
                except PermissionError:
                    pass  # Skip directories with no permission
                finally:
                    dir_queue.task_done()
        
        worker_count = 64
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            for _ in range(worker_count):
                executor.submit(worker)
            dir_queue.join()
        
        return matches

    def scan_all_files(self, paths: list[str]) -> list[str]:
        """Scan directories once and return all file paths found."""
        all_files = []
        lock = threading.Lock()
        dir_queue = Queue()
        for p in paths:
            dir_queue.put(p)
        
        def worker():
            while True:
                try:
                    current_dir = dir_queue.get_nowait()
                except Empty:
                    break
                try:
                    for entry in os.scandir(current_dir):
                        if entry.is_file():
                            with lock:
                                all_files.append(entry.path)
                        elif entry.is_dir():
                            dir_queue.put(entry.path)
                except PermissionError:
                    pass
                finally:
                    dir_queue.task_done()
        
        worker_count = 64
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            for _ in range(worker_count):
                executor.submit(worker)
            dir_queue.join()
        
        return all_files

    def list_installed_applications(self) -> list[str]:
        """List installed applications from the Windows registry."""
        applications = []
        uninstall_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, uninstall_key) as key:
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, subkey_name) as subkey:
                        name = winreg.QueryValueEx(subkey, 'DisplayName')[0]
                        applications.append(name)
                except FileNotFoundError:
                    continue
        return applications
