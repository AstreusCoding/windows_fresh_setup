import os
import fnmatch
from concurrent.futures import ThreadPoolExecutor
import winreg
from typing import Callable, Optional, List
import threading
from queue import Queue, Empty


class FileScraper:
    """
    A class for performing concurrent file scanning and retrieving system information.

    This class provides methods to:
      - Find files matching a specific pattern in a set of directories.
      - Recursively scan directories for all file paths.
      - List installed applications from the Windows registry.
    """

    def __init__(self) -> None:
        """
        Initialize a FileScraper with default file patterns for text, image, and video files.
        """
        self.text_file_pattern: str = '*.txt'
        self.image_patterns: List[str] = ['*.png', '*.jpg', '*.jpeg', '*.gif']
        self.video_patterns: List[str] = ['*.mp4', '*.avi', '*.mkv']

    def find_files(
        self,
        pattern: str,
        paths: List[str],
        file_found_callback: Optional[Callable[[str], None]] = None
    ) -> List[str]:
        """
        Find files matching the specified pattern in the provided directories concurrently.

        This method uses a queue with a pool of worker threads to traverse the directory
        tree and collect file paths matching the glob pattern.

        Parameters:
            pattern: The file name pattern to match (e.g., '*.txt').
            paths: A list of directory paths in which to search.
            file_found_callback: An optional callback function invoked with each found file path.

        Returns:
            A list of file paths that match the provided pattern.
        """
        matches: List[str] = []
        lock = threading.Lock()
        dir_queue: Queue[str] = Queue()

        # Enqueue initial directories.
        for p in paths:
            dir_queue.put(p)

        def worker() -> None:
            """
            Worker function to process directories from the queue and search for matching files.
            """
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
                    # Skip directories where permission is denied.
                    pass
                finally:
                    dir_queue.task_done()

        # Use a pool of worker threads.
        worker_count = 64
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            for _ in range(worker_count):
                executor.submit(worker)
            dir_queue.join()

        return matches

    def scan_all_files(self, paths: List[str]) -> List[str]:
        """
        Recursively scan the provided directories and return all file paths found.

        This method uses a concurrent approach to traverse directories and collect file paths.

        Parameters:
            paths: A list of directory paths to scan.

        Returns:
            A list of all file paths discovered during the scan.
        """
        all_files: List[str] = []
        lock = threading.Lock()
        dir_queue: Queue[str] = Queue()

        # Enqueue the initial directory paths.
        for p in paths:
            dir_queue.put(p)

        def worker() -> None:
            """
            Worker function to traverse directories from the queue and collect file paths.
            """
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
                    # Skip directories that cannot be accessed.
                    pass
                finally:
                    dir_queue.task_done()

        worker_count = 64
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            for _ in range(worker_count):
                executor.submit(worker)
            dir_queue.join()

        return all_files

    def list_installed_applications(self) -> List[str]:
        """
        Retrieve a list of installed applications from the Windows registry.

        The method queries the Uninstall registry key for installed applications and
        returns the list of display names.

        Returns:
            A list of application names installed on the system.
        """
        applications: List[str] = []
        uninstall_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, uninstall_key) as key:
                num_subkeys = winreg.QueryInfoKey(key)[0]
                for i in range(num_subkeys):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            name = winreg.QueryValueEx(subkey, 'DisplayName')[0]
                            applications.append(name)
                    except OSError:
                        # Skip keys without a DisplayName or inaccessible keys.
                        continue
        except Exception as e:
            # Log or handle exception as needed.
            print(f"Error accessing registry: {e}")
        return applications
