# Windows File Scraper & Backup Tool

A GUI tool to scan, filter, and backup files from Windows systems. Supports selective scanning of user directories and custom folder filtering.

## Features

- Scan for specific file types (text, images, videos)
- Full system scan capability
- Configurable folder exclusions
- User profile selection
- File backup with category organization
- Progress tracking with elapsed time
- Settings persistence

## Requirements

- Python 3.8+
- Windows OS

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/windows-file-scraper.git
cd windows-file-scraper
```plaintext

## Usage

1. Run the application:

```bash
python src/main.py
```

1. Configure settings:
   - Click "Settings" to select user profiles to scan
   - Add folders to skip
   - Block specific folders from search results

2. Start scanning:
   - Use individual scan buttons for specific file types
   - Use "Full Scan" for all supported file types
   - Monitor progress and current file being processed

3. Backup files:
   - After a scan completes, use "Backup Files" button
   - Choose between categorized or original structure backup
   - Files are backed up to ./backups directory with timestamp

## Structure

```plaintext
windows-file-scraper/
├── src/
│   ├── main.py
│   ├── ui.py
│   └── scraper.py
├── backups/
├── requirements.txt
├── README.md
└── .gitignore
```
