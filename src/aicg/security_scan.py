"""Normalize a real Bandit scan for the security gate."""

import json
import subprocess
import sys


def main() -> int:
    result = subprocess.run(  # nosec B603: fixed module command plus user-selected scan paths
        [sys.executable, "-m", "bandit", "-r", *(sys.argv[1:] or ["src"]), "-f", "json", "-q"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode not in {0, 1}:
        print("Bandit failed to execute", file=sys.stderr)
        return 2
    try:
        report = json.loads(result.stdout)
        if report.get("errors") or not report.get("metrics", {}).get("_totals", {}).get("loc", 0):
            raise ValueError("scan incomplete")
        findings = report["results"]
        print(json.dumps({"critical": 0, "high": sum(item["issue_severity"] == "HIGH" for item in findings)}))
    except (ValueError, KeyError, TypeError):
        print("Invalid or incomplete Bandit report", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
