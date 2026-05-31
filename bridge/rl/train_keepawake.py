"""
Wrapper that prevents Windows from sleeping while training runs.

Calls Windows' SetThreadExecutionState with ES_CONTINUOUS | ES_SYSTEM_REQUIRED
which tells the OS "this process is doing important work, don't go to sleep."
Settings are restored automatically when the script exits (including via
Ctrl+C or a crash).

Pass any args you'd normally pass to train_masked.py — they're forwarded.

Run:
    python bridge/rl/train_keepawake.py --checkpoint checkpoints/maskppo_v3_768_steps.zip --steps 20000 --save checkpoints/maskppo_v4.zip
"""

from __future__ import annotations

import atexit
import ctypes
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

# Windows ExecutionState flags
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002  # also keep screen on if you want; off by default
ES_AWAYMODE_REQUIRED = 0x00000040  # background-app mode (no UI). useful for servers.


def keep_system_awake(allow_display_sleep: bool = True):
    """Tell Windows not to sleep until this process exits."""
    if sys.platform != "win32":
        print("[keepawake] not on Windows, no-op")
        return
    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
    if not allow_display_sleep:
        flags |= ES_DISPLAY_REQUIRED
    ctypes.windll.kernel32.SetThreadExecutionState(flags)
    print(f"[keepawake] system sleep disabled (display sleep "
          f"{'enabled' if allow_display_sleep else 'disabled'})")

    def _restore():
        # Restore default behavior: just ES_CONTINUOUS clears the request.
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        print("[keepawake] system sleep restored")
    atexit.register(_restore)


def main() -> int:
    keep_system_awake(allow_display_sleep=True)
    # Forward to train_masked.main with the original argv.
    from rl.train_masked import main as train_main
    return train_main()


if __name__ == "__main__":
    sys.exit(main())
