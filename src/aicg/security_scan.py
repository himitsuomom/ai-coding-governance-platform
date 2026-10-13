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
        if not isinstance(report, dict):
            raise ValueError("missing Bandit report object")
        errors = report.get("errors")
        metrics = report.get("metrics")
        if not isinstance(errors, list) or errors or not isinstance(metrics, dict):
            raise ValueError("missing or failed Bandit scan metadata")
        totals = metrics.get("_totals")
        if not isinstance(totals, dict):
            raise ValueError("missing Bandit scan totals")
        loc = totals.get("loc")
        if not isinstance(loc, int) or isinstance(loc, bool) or loc <= 0:
            raise ValueError("no valid lines of code scanned")
        findings = report.get("results")
        if not isinstance(findings, list):
            raise ValueError("missing Bandit findings list")
        high = 0
        for finding in findings:
            if not isinstance(finding, dict) or finding.get("issue_severity") not in {
                "LOW", "MEDIUM", "HIGH"
            }:
                raise ValueError("invalid Bandit finding severity")
            high += finding["issue_severity"] == "HIGH"
        print(json.dumps({"critical": 0, "high": high}))
    except (ValueError, KeyError, TypeError):
        print("Invalid or incomplete Bandit report", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
