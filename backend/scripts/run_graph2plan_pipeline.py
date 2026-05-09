"""Run Graph2Plan data preprocessing and training steps from Archi3D workspace.

Usage examples:
  python scripts/run_graph2plan_pipeline.py --preprocess
  python scripts/run_graph2plan_pipeline.py --preprocess --steps 1,2,3
  python scripts/run_graph2plan_pipeline.py --train --train-args "--epoch 30 --batch_size 8"
  python scripts/run_graph2plan_pipeline.py --preprocess --train --split
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


PREPROCESS_SCRIPTS = {
    1: "1.tf_train.py",
    2: "2.data_train_converted.py",
    3: "3.rNum_train.py",
    4: "4.data_train_eNum.py",
    5: "5.data_test_converted.py",
    6: "6.cluster.py",
}


def _run_step(step: list[str], cwd: Path) -> None:
    print(f"\n[graph2plan] running: {' '.join(step)}")
    proc = subprocess.run(step, cwd=str(cwd), check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {proc.returncode}: {' '.join(step)}"
        )


def _validate_root(root: Path) -> None:
    required = [
        root / "DataPreparation",
        root / "Network",
        root / "DataPreparation" / "config.py",
        root / "Network" / "train.py",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Graph2Plan folder appears incomplete. Missing: " + ", ".join(missing)
        )


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    backend_root = script_dir.parent
    workspace_root = backend_root.parent
    backend_graph2plan = backend_root / "Graph2plan-master"
    workspace_graph2plan = workspace_root / "Graph2plan-master"
    default_root = backend_graph2plan if backend_graph2plan.exists() else workspace_graph2plan

    parser = argparse.ArgumentParser(description="Run Graph2Plan pipeline scripts.")
    parser.add_argument(
        "--graph2plan-root",
        default=str(default_root),
        help="Path to Graph2plan-master root folder.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable for running Graph2Plan scripts.",
    )
    parser.add_argument(
        "--preprocess",
        action="store_true",
        help="Run DataPreparation scripts in sequence.",
    )
    parser.add_argument(
        "--steps",
        default="1,2,3,4,5,6",
        help="Comma-separated DataPreparation steps to run (subset of 1..6).",
    )
    parser.add_argument(
        "--split",
        action="store_true",
        help="Run Network/split.py before training.",
    )
    parser.add_argument(
        "--train",
        action="store_true",
        help="Run Network/train.py.",
    )
    parser.add_argument(
        "--train-args",
        default="",
        help="Extra args passed to Network/train.py (quoted string).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.graph2plan_root).resolve()
    _validate_root(root)

    if not args.preprocess and not args.train and not args.split:
        print("Nothing to run. Pass --preprocess and/or --train and/or --split.")
        return 0

    python_exec = args.python
    data_prep_dir = root / "DataPreparation"
    network_dir = root / "Network"

    if args.preprocess:
        raw_steps = [part.strip() for part in str(args.steps).split(",") if part.strip()]
        steps = []
        for part in raw_steps:
            step_num = int(part)
            if step_num not in PREPROCESS_SCRIPTS:
                raise ValueError(f"Unsupported preprocess step: {step_num}")
            steps.append(step_num)

        for step_num in steps:
            _run_step([python_exec, PREPROCESS_SCRIPTS[step_num]], cwd=data_prep_dir)

    if args.split:
        _run_step([python_exec, "split.py"], cwd=network_dir)

    if args.train:
        train_cmd = [python_exec, "train.py"]
        if args.train_args.strip():
            train_cmd.extend(shlex.split(args.train_args))
        _run_step(train_cmd, cwd=network_dir)

    print("\n[graph2plan] completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
