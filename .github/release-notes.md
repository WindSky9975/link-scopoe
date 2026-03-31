## LinkScope Release

LinkScope is a local Windows desktop tool for scanning and managing directory junctions and symbolic links.

### Included In This Release

- `LinkScope-*-windows-x64.zip`
- `LinkScope.exe` packaged as a single-file Windows application

### Highlights

- Scan a root folder recursively for junctions and symlinks
- Filter results by link type, link drive, and target drive
- Create or delete junctions and symlinks from the desktop UI
- Open link paths, open targets, and reveal items in File Explorer

### Requirements

- Windows with NTFS support
- No Python runtime is required for the packaged `exe`
- Creating symlinks may require administrator privileges or Windows Developer Mode

### Notes

- This project is Windows-only
- Directory junction targets must already exist
