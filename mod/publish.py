"""
Publish a built mod zip to the Factorio Mod Portal via API.

Two-step API flow (https://wiki.factorio.com/Mod_portal_API):
  1. POST init_upload   ->  upload_url
  2. POST upload_url    ->  finalized version

Requires the FACTORIO_MODS_API_KEY env var. On Windows, falls back to
reading it from the User-level env var via the registry — useful when the
current process inherited an environment older than the most recent setx
(e.g. a long-running VSCode session).

The mod must already exist on the portal. First-time publish has to go
through the web form because the API doesn't accept metadata fields
(title, description, license, category). All subsequent version pushes
can use this script.

Run:
    python mod/publish.py --dry-run                 # auth check only
    python mod/publish.py                           # build current dist + push
    python mod/publish.py --zip path/to/file.zip    # push a specific file
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

INIT_URL = "https://mods.factorio.com/api/v2/mods/releases/init_upload"


def get_api_key() -> str | None:
    key = os.environ.get("FACTORIO_MODS_API_KEY")
    if key:
        return key
    if os.name == "nt":
        # Fall back to reading the user-level env var directly from the
        # registry, in case setx ran but no fresh process picked it up yet.
        import subprocess
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                '[Environment]::GetEnvironmentVariable("FACTORIO_MODS_API_KEY","User")',
            ],
            capture_output=True, text=True, check=False,
        )
        key = result.stdout.strip()
        return key or None
    return None


def init_upload(mod_name: str, api_key: str) -> dict:
    data = urllib.parse.urlencode({"mod": mod_name}).encode()
    req = urllib.request.Request(
        INIT_URL, data=data, method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def upload_file(upload_url: str, zip_path: Path) -> dict:
    boundary = "----claude-companion-multipart-boundary"
    body = b""
    body += f"--{boundary}\r\n".encode()
    body += (
        f'Content-Disposition: form-data; name="file"; '
        f'filename="{zip_path.name}"\r\n'
    ).encode()
    body += b"Content-Type: application/zip\r\n\r\n"
    body += zip_path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        upload_url, data=body, method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main() -> int:
    p = argparse.ArgumentParser(description="Publish built mod to Factorio mod portal.")
    p.add_argument("--dry-run", action="store_true",
                   help="only call init_upload (proves auth + mod exists); don't push the file")
    p.add_argument("--zip", default=None,
                   help="path to the .zip; if omitted, picks the latest in mod/dist/")
    p.add_argument("--mod", default="claude-companion",
                   help="mod name as it appears on the portal")
    args = p.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("[publish] FACTORIO_MODS_API_KEY not set anywhere reachable", file=sys.stderr)
        print("[publish] run: setx FACTORIO_MODS_API_KEY \"<key>\"", file=sys.stderr)
        return 1
    print(f"[publish] api key found ({len(api_key)} chars, prefix {api_key[:4]}...)")

    if args.zip:
        zip_path = Path(args.zip)
    else:
        dist_dir = Path(__file__).resolve().parent / "dist"
        candidates = sorted(dist_dir.glob(f"{args.mod}_*.zip"))
        if not candidates:
            print(f"[publish] no zip found in {dist_dir}; run deploy.ps1 first", file=sys.stderr)
            return 2
        zip_path = candidates[-1]
    if not zip_path.exists():
        print(f"[publish] {zip_path} does not exist", file=sys.stderr)
        return 2
    print(f"[publish] zip: {zip_path} ({zip_path.stat().st_size} bytes)")

    try:
        init = init_upload(args.mod, api_key)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[publish] init_upload failed ({e.code}): {body}", file=sys.stderr)
        return 3
    upload_url = init.get("upload_url")
    if not upload_url:
        print(f"[publish] init_upload returned no upload_url: {init}", file=sys.stderr)
        return 4
    # Don't print the full upload_url (it's a signed token); truncate.
    print(f"[publish] init_upload OK (upload_url received, {len(upload_url)} chars)")

    if args.dry_run:
        print("[publish] --dry-run: skipping actual upload. auth + mod exists confirmed.")
        return 0

    try:
        result = upload_file(upload_url, zip_path)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[publish] upload failed ({e.code}): {body}", file=sys.stderr)
        return 5

    print("[publish] success!")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
