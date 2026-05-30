"""
Dump every parameter of a saved PPO checkpoint as a single text file.

Format per layer:
    === <param_name>  shape=<tuple>  count=<n> ===
    <value> <value> <value> ... (16 per line, 6-digit precision)

Run:
    python bridge/rl/dump_weights.py --checkpoint checkpoints/bc_warm.zip
        --out checkpoints/bc_warm_weights.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from stable_baselines3 import PPO  # noqa: E402

VALS_PER_LINE = 16


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    ckpt = Path(args.checkpoint)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"[dump] loading {ckpt} ...")
    model = PPO.load(str(ckpt))
    total = 0
    with out.open("w", encoding="utf-8") as f:
        f.write(f"# weights dump of {ckpt.name}\n")
        f.write(f"# format: per layer header, then values (16/line, 6 decimals)\n\n")
        for name, tensor in model.policy.named_parameters():
            flat = tensor.detach().cpu().numpy().reshape(-1)
            n = flat.size
            total += n
            f.write(f"=== {name}  shape={tuple(tensor.shape)}  count={n} ===\n")
            for i in range(0, n, VALS_PER_LINE):
                chunk = flat[i:i + VALS_PER_LINE]
                f.write(" ".join(f"{v:+.6f}" for v in chunk) + "\n")
            f.write("\n")
        f.write(f"# total parameters: {total:,}\n")

    print(f"[dump] wrote {total:,} weights to {out}  ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
