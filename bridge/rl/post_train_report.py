"""
One-shot post-training report. Reads the JSONL logs + runs N eval episodes
+ summarizes everything into a markdown file.

Run (after training finishes / is stopped):
    python bridge/rl/post_train_report.py --run chain_v2 --eval-episodes 10

Reads:
  checkpoints/maskppo_<run>.zip             (final model)
  checkpoints/maskppo_<run>_best.zip        (best-by-ep-rew-mean)
  checkpoints/maskppo_<run>_episodes.jsonl  (per-episode r/l from sb3 Monitor)
  checkpoints/maskppo_<run>_info.jsonl      (per-episode info dict, NEW runs only)
Writes:
  reports/<run>_report.md                   (the rollup)
  reports/<run>_curve.png                   (training curve, if matplotlib)
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, help="run name (e.g. chain_v2)")
    p.add_argument("--ckpt-dir", default="checkpoints")
    p.add_argument("--reports-dir", default="reports")
    p.add_argument("--eval-episodes", type=int, default=10)
    p.add_argument("--skip-eval", action="store_true",
                   help="don't run eval (just summarize JSONL)")
    args = p.parse_args()

    ckpt_dir = Path(args.ckpt_dir)
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    final_ckpt = ckpt_dir / f"maskppo_{args.run}.zip"
    best_ckpt = ckpt_dir / f"maskppo_{args.run}_best.zip"
    episodes_jsonl = ckpt_dir / f"maskppo_{args.run}_episodes.jsonl"
    info_jsonl = ckpt_dir / f"maskppo_{args.run}_info.jsonl"

    lines: list[str] = []
    lines.append(f"# Training Report — {args.run}\n")
    lines.append("## Files\n")
    for f in (final_ckpt, best_ckpt, episodes_jsonl, info_jsonl):
        exists = "yes" if f.exists() else "MISSING"
        size = f.stat().st_size if f.exists() else 0
        lines.append(f"- `{f.name}`: {exists} ({size:,} bytes)")
    lines.append("")

    # Episode summary from jsonl
    if episodes_jsonl.exists():
        eps = [json.loads(L) for L in episodes_jsonl.read_text(encoding="utf-8").splitlines() if L.strip()]
        if eps:
            rewards = [e["r"] for e in eps]
            lengths = [e["l"] for e in eps]
            lines.append("## Training reward summary\n")
            lines.append(f"- Episodes: **{len(eps)}**")
            lines.append(f"- Reward mean: **{statistics.mean(rewards):+.2f}** "
                         f"(stdev {statistics.pstdev(rewards):.1f})")
            lines.append(f"- Reward min/max: {min(rewards):+.1f} / {max(rewards):+.1f}")
            lines.append(f"- Length mean/max: {statistics.mean(lengths):.1f} / {max(lengths)}")
            if len(rewards) >= 20:
                early = statistics.mean(rewards[:20])
                late = statistics.mean(rewards[-20:])
                lines.append(f"- First 20 vs last 20 mean: {early:+.1f} -> {late:+.1f}  "
                             f"(delta **{late-early:+.1f}**)")
            best_idx = max(range(len(rewards)), key=lambda i: rewards[i])
            lines.append(f"- Best training episode: #{best_idx+1} reward={rewards[best_idx]:+.1f}")
            lines.append("")

    # Info summary (if present from newer runs)
    if info_jsonl.exists():
        infos = [json.loads(L) for L in info_jsonl.read_text(encoding="utf-8").splitlines() if L.strip()]
        if infos:
            reached_count = sum(1 for i in infos if i.get("reached"))
            outputs = [i.get("output_count") or 0 for i in infos]
            lines.append("## Episode info summary\n")
            lines.append(f"- Episodes with full info: **{len(infos)}**")
            lines.append(f"- Reached target: {reached_count}/{len(infos)} "
                         f"({100*reached_count/len(infos):.0f}%)")
            lines.append(f"- Output gears mean/max: {statistics.mean(outputs):.1f} / {max(outputs)}")
            lines.append("")
            # Component breakdown of last 20 episodes
            recent = infos[-20:]
            comps = {}
            for ep in recent:
                c = ep.get("components") or {}
                if isinstance(c, dict):
                    for k, v in c.items():
                        if isinstance(v, (int, float)):
                            comps.setdefault(k, []).append(v)
            if comps:
                lines.append("### Mean reward components (last 20 episodes)\n")
                for k in sorted(comps.keys()):
                    lines.append(f"- {k}: {statistics.mean(comps[k]):+.2f}")
                lines.append("")

    # Curve plot
    if episodes_jsonl.exists():
        curve_png = reports_dir / f"{args.run}_curve.png"
        try:
            subprocess.run([sys.executable, str(_BRIDGE / "rl" / "plot_episodes.py"),
                            "--jsonl", str(episodes_jsonl),
                            "--save", str(curve_png)], check=True)
            lines.append(f"## Training curve\n\n![curve]({curve_png.name})\n")
        except subprocess.CalledProcessError as e:
            lines.append(f"## Training curve\n\nplot failed: {e}\n")

    # Eval — needs RCON env
    if not args.skip_eval and best_ckpt.exists():
        lines.append(f"## Eval — {args.eval_episodes} deterministic episodes against best ckpt\n")
        try:
            result = subprocess.run(
                [sys.executable, str(_BRIDGE / "rl" / "eval_checkpoint.py"),
                 "--checkpoint", str(best_ckpt),
                 "--episodes", str(args.eval_episodes)],
                check=False, capture_output=True, text=True,
            )
            lines.append("```")
            lines.append(result.stdout)
            if result.stderr:
                lines.append("--- stderr ---")
                lines.append(result.stderr)
            lines.append("```\n")
        except Exception as e:
            lines.append(f"eval failed: {e}\n")
    elif args.skip_eval:
        lines.append("## Eval\n\nskipped per --skip-eval\n")
    else:
        lines.append(f"## Eval\n\nbest ckpt not found: {best_ckpt}\n")

    out_path = reports_dir / f"{args.run}_report.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[report] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
