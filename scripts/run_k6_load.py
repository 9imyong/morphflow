#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import Path


def _parse_vus(raw: str) -> list[int]:
    values: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        value = int(token)
        if value <= 0:
            raise ValueError(f"VUS must be positive: {value}")
        values.append(value)
    if not values:
        raise ValueError("At least one VUS value is required")
    return values


def _build_output_path(out_dir: Path, mode_label: str, vus: int) -> Path:
    suffix = f"_{mode_label}" if mode_label else ""
    return out_dir / f"k6{suffix}_vus{vus}.json"


def _run_command(cmd: list[str], cwd: Path) -> None:
    print("$ " + " ".join(shlex.quote(part) for part in cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run k6 load tests via docker and export summary JSON files.")
    parser.add_argument("--vus", default="10,30,50", help="Comma-separated VU list (default: 10,30,50)")
    parser.add_argument("--duration", default="1m", help="k6 duration (default: 1m)")
    parser.add_argument("--base-url", default="http://host.docker.internal:8000", help="API base URL")
    parser.add_argument("--mode-label", default="", help="Output label (e.g. bmode, cmode)")
    parser.add_argument("--script", default="../tests/perf/jobs_load_test.js", help="k6 script path")
    parser.add_argument("--out-dir", default="../reports/perf", help="Output directory for summary files")
    parser.add_argument("--k6-image", default="grafana/k6", help="Docker image for k6")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    out_dir = (repo_root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    vus_values = _parse_vus(args.vus)

    for vus in vus_values:
        out_path = _build_output_path(out_dir, args.mode_label, vus)
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{repo_root}:/work",
            "-w",
            "/work",
            args.k6_image,
            "run",
            args.script,
            "-e",
            f"BASE_URL={args.base_url}",
            "-e",
            f"VUS={vus}",
            "-e",
            f"DURATION={args.duration}",
            "--summary-export",
            str(out_path),
        ]
        _run_command(cmd, cwd=repo_root)
        print(f"saved: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
