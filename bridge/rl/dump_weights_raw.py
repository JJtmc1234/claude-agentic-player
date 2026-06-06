"""Dump raw weights of a MaskablePPO checkpoint as numbers only — no
layer names, no shapes, no headers. Each weight on its own line, full
precision.

Run:
    python bridge/rl/dump_weights_raw.py --checkpoint <ckpt.zip> --out <out.txt>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from sb3_contrib import MaskablePPO


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    ckpt = Path(args.checkpoint)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    model = MaskablePPO.load(str(ckpt))
    total = 0
    with out.open("w", encoding="utf-8") as f:
        for _, tensor in model.policy.named_parameters():
            flat = tensor.detach().cpu().numpy().reshape(-1)
            for v in flat:
                f.write(f"{v}\n")
            total += flat.size

    print(f"[dump] wrote {total:,} weights to {out}  ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
