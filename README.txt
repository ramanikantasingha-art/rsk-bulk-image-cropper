BULK IMAGE CROPPER 2.0

START ON WINDOWS
1. Extract the entire ZIP. Do not run from inside the ZIP.
2. Double-click START_CROPPER.bat.
3. If it reports missing dependencies, run SETUP_WINDOWS.bat once.
   Setup needs internet and Python (3.11 or 3.12 recommended).
4. For future use, run START_CROPPER.bat. It does not reinstall packages.

UPDATING AN EXISTING INSTALLATION
Copy bulk_image_cropper.py and START_CROPPER.bat into your existing app
folder alongside its .venv or venv folder. Start with START_CROPPER.bat.
This reuses the existing environment and avoids reinstalling dependencies.

CUSTOMIZE THE CROP
- Drag any corner or edge handle to change the crop dimensions.
- You can also drag directly on a selection edge.
- Drag inside the blue selection to move it without changing its size.
- Drag outside the selection to draw a replacement rectangle.
- Shift-drag anywhere to draw a replacement rectangle.
- Press Escape during a drag to restore the preceding rectangle.
- Edit X, Y, W and H for exact pixel measurements.
- Lock aspect ratio to retain the current width-to-height proportion.
- Select full image resets the selection to the image boundaries.

BATCH WORK
Choose input and output folders. Preview images with Previous and Next.
The crop position is retained across images. Apply to all images exports
all input files using the same pixel rectangle. Uncheck it to export only
the displayed file. For smaller images, the crop is clipped to their edges;
images that do not overlap the rectangle are reported as failures.
Selections are not permanently saved between application sessions.

OUTPUT
PNG is lossless. JPEG quality is adjustable; JPEG is re-encoded.
Output names match input names, so existing output files may be replaced.
Use a separate empty output folder to preserve previous work.

TROUBLESHOOTING
Use START_CROPPER.bat instead of double-clicking the Python file.
The launcher stays open and saves cropper_startup_log.txt. Python errors
also go to crash_log.txt, with a Windows error dialog where possible.
If startup fails, send the log or a screenshot of the console.
The ZIP includes source code, not a standalone Windows EXE or Python runtime.

VALIDATION
Offscreen Qt tests cover all eight resize handles with free and locked
aspect ratios, movement, boundaries, replacement selection, numerical file
ordering, navigation, resized windows, smaller-image previews and both
current-image and bulk export sizes. Run python test_cropper.py to repeat.
Windows launcher and setup scripts have been reviewed but have not been
executed on Windows in the build environment.
