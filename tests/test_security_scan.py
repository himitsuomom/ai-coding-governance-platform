"""Regression tests for the Bandit-to-security-gate JSON adapter."""

import json
from types import SimpleNamespace

import pytest

from aicg import security_scan


def run_report(monkeypatch, capsys, report, returncode=0):
    def fake_run(command, **kwargs):
        assert command[1:3] == ["-m", "bandit"]
        assert command[command.index("-f") + 1] == "json"
        assert kwargs["check"] is False
        return SimpleNamespace(returncode=returncode, stdout=json.dumps(report))

    monkeypatch.setattr(security_scan.subprocess, "run", fake_run)
    code = security_scan.main()
    return code, capsys.readouterr()


def valid_report(findings=None):
    return {"errors": [], "metrics": {"_totals": {"loc": 20}}, "results": findings or []}


def test_bandit_valid_scan_counts_high_only(monkeypatch, capsys):
    report = valid_report([
        {"issue_severity": "LOW"},
        {"issue_severity": "MEDIUM"},
        {"issue_severity": "HIGH"},
        {"issue_severity": "HIGH"},
    ])
    code, output = run_report(monkeypatch, capsys, report, returncode=1)
    assert code == 0
    assert json.loads(output.out) == {"critical": 0, "high": 2}
    assert output.err == ""


def test_bandit_clean_scan(monkeypatch, capsys):
    code, output = run_report(monkeypatch, capsys, valid_report())
    assert code == 0
    assert json.loads(output.out) == {"critical": 0, "high": 0}


@pytest.mark.parametrize("report", [
    {"metrics": {"_totals": {"loc": 20}}, "results": []},  # Missing errors status
    {"errors": "none", "metrics": {"_totals": {"loc": 20}}, "results": []},
    {"errors": ["parse error"], "metrics": {"_totals": {"loc": 20}}, "results": []},
    {"errors": [], "metrics": {}, "results": []},
    {"errors": [], "metrics": {"_totals": {"loc": 0}}, "results": []},
    {"errors": [], "metrics": {"_totals": {"loc": True}}, "results": []},
    {"errors": [], "metrics": {"_totals": {"loc": 20}}},  # Missing results
    {"errors": [], "metrics": {"_totals": {"loc": 20}}, "results": {}},
    valid_report([{}]),
    valid_report([{"issue_severity": "CRITICAL"}]),  # Unknown severity must not count as zero
    valid_report([{"issue_severity": None}]),
])
def test_bandit_malformed_report_rejected(monkeypatch, capsys, report):
    code, output = run_report(monkeypatch, capsys, report)
    assert code == 2
    assert output.out == ""
    assert "Invalid or incomplete Bandit report" in output.err


def test_bandit_execution_error_rejected(monkeypatch, capsys):
    code, output = run_report(monkeypatch, capsys, valid_report(), returncode=2)
    assert code == 2
    assert output.out == ""
    assert "Bandit failed to execute" in output.err
