# Bulk Image Cropper v2

A Windows desktop application for applying a consistent pixel crop to a folder of images. Built with **Python, PyQt5, and Pillow**.

## Features

- Select an image folder, preview images, and set a crop rectangle interactively.
- Adjust all eight resize handles, reposition the rectangle, or specify X/Y/width/height numerically.
- Optionally lock the crop aspect ratio.
- Apply the same crop to the current image or the whole folder.
- Export PNG or JPEG; browse input filenames in natural numerical order.
- Write startup and crash diagnostics to local log files.

## Requirements

- Windows with Python installed (Python 3.11 or 3.12 recommended by the original project instructions).
- Internet connection for first-time Python dependency installation.
- Dependencies in [`requirements.txt`](requirements.txt): PyQt5 and Pillow.

## Start on Windows

1. Download the repository as a ZIP from **Code > Download ZIP** and extract it.
2. Run **`SETUP_WINDOWS.bat`** once to create a local `.venv` and install dependencies.
3. Double-click **`START_CROPPER.bat`** to launch the application.
4. On later starts, run **`START_CROPPER.bat`**; you don't need to reinstall packages.

Alternatively, from a terminal with dependencies already installed:

```powershell
python -m pip install -r requirements.txt
python bulk_image_cropper.py
```

## Usage and data safety

1. Choose the **input** image folder and a **separate output** folder.
2. Preview an image and draw or adjust your desired crop.
3. Export only the displayed image or select **Apply to all** for a batch.
4. Check output files before deleting or replacing originals.

**Warning:** Output filenames mirror their inputs; existing files in the selected output folder can be overwritten. JPEG is re-encoded; PNG export is lossless. Crop selections are not persisted between sessions.

## Testing

An offscreen GUI test script is included:

```powershell
python test_cropper.py
```

It exercises selection handles, bounds, navigation and export using temporary test images. A static source check alone is *not* a substitute for actually running the GUI on Windows.

## Repository files

| File | Purpose |
| --- | --- |
| `bulk_image_cropper.py` | Main application |
| `START_CROPPER.bat` | Windows launcher with logging |
| `SETUP_WINDOWS.bat` | One-time Windows environment setup |
| `requirements.txt` | Python dependencies |
| `test_cropper.py` | Offscreen GUI tests |
| `README.txt` | Original user instructions |
| `README.md` | GitHub project overview |
| `.gitignore` | Keeps local environments and logs out of Git |

### Notes

This repository contains **source code**, not a portable `.exe` or bundled Python installation. Avoid committing private customer images or data. Do not upload `.venv`, credentials, or locally generated crash logs to a public repository.
