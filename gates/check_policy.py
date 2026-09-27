"""Compatibility entry point; all enforcement lives in the package."""

from pathlib import Path

from aicg.cli import main

root = str(Path(__file__).resolve().parents[1])
result = main(["--root", root, "gate", "run"])
raise SystemExit(result if result else main(["--root", root, "gate", "final"]))
