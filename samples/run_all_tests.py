"""Run every ``samples/test_*.py`` smoke test and report a summary.

Each test is a standalone script that exits non-zero on failure, so this runner
just executes them one after another in a subprocess (isolated state, a hard
timeout per file) and prints a PASS / FAIL / TIMEOUT line for each.

Usage (from the backend repo root or anywhere):
    python samples/run_all_tests.py                 # run all
    python samples/run_all_tests.py -k ansi grid    # only files whose name contains a term
    python samples/run_all_tests.py --timeout 900   # per-file timeout in seconds (default 600)

Exit code is 0 only when every selected test passed.
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
import time

SAMPLES_DIR = os.path.dirname(os.path.abspath(__file__))


def discover(terms: list[str]) -> list[str]:
    files = sorted(glob.glob(os.path.join(SAMPLES_DIR, "test_*.py")))
    if terms:
        files = [f for f in files if any(t.lower() in os.path.basename(f).lower() for t in terms)]
    return files


def run_one(path: str, timeout: int) -> tuple[str, float, str]:
    env = dict(os.environ)
    # Windows consoles default to a legacy code page; force UTF-8 so unicode prints do not crash a test.
    env.setdefault("PYTHONIOENCODING", "utf-8")
    start = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, path],
            cwd=os.path.dirname(SAMPLES_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT", time.time() - start, f"no result after {timeout}s"
    elapsed = time.time() - start
    if proc.returncode == 0:
        return "PASS", elapsed, ""
    tail = (proc.stderr or proc.stdout or "").strip().splitlines()
    return "FAIL", elapsed, tail[-1] if tail else f"exit code {proc.returncode}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-k", "--keywords", nargs="*", default=[], help="only run files whose name contains one of these")
    parser.add_argument("--timeout", type=int, default=600, help="per-file timeout in seconds")
    args = parser.parse_args()

    files = discover(args.keywords)
    if not files:
        print("No matching samples/test_*.py files found.")
        return 1

    results = []
    for path in files:
        name = os.path.basename(path)
        print(f"-> {name} ...", flush=True)
        status, elapsed, detail = run_one(path, args.timeout)
        results.append((name, status, elapsed, detail))
        suffix = f"  [{detail}]" if detail and status != "PASS" else ""
        print(f"   {status} in {elapsed:.1f}s{suffix}", flush=True)

    print("\nSummary")
    for name, status, elapsed, _ in results:
        print(f"  {status:8} {elapsed:7.1f}s  {name}")
    failed = [r for r in results if r[1] != "PASS"]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
