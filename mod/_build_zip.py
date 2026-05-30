"""
Zip a folder using POSIX (forward-slash) path separators inside the archive.

Why this exists: PowerShell's Compress-Archive embeds Windows backslashes in
zip entry names, and the Factorio mod portal rejects such uploads ("Your ZIP
archive is using Windows-style backslashes"). Python's zipfile + a manual
replace of os.sep -> '/' produces a cross-platform-safe archive.

Usage:
    python _build_zip.py <source_folder> <destination_zip>

The source folder itself becomes the top-level directory inside the zip
(matches Factorio's mod-zip convention: claude-companion_0.2.0/info.json).
"""

import os
import sys
import zipfile


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python _build_zip.py <source_folder> <destination_zip>",
              file=sys.stderr)
        return 1
    src = os.path.abspath(sys.argv[1])
    dest = os.path.abspath(sys.argv[2])
    if not os.path.isdir(src):
        print(f"not a directory: {src}", file=sys.stderr)
        return 2
    parent = os.path.dirname(src)
    count = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(src):
            for f in files:
                abs_path = os.path.join(root, f)
                rel_path = os.path.relpath(abs_path, parent).replace(os.sep, "/")
                zf.write(abs_path, rel_path)
                count += 1
    print(f"wrote {dest} ({count} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
