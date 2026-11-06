"""Regression checks for request-input handling in app.py.

* frequency values come from the browser; they must be parsed, never executed.
* the Flask app still answers a plain GET after the changes.

Run with ``python samples/test_request_hardening.py``.
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def check_parse_frequency(app_module) -> None:
    parse = app_module._parse_frequency
    assert parse("50") == 50.0
    assert parse(60) == 60.0
    assert parse("60.0") == 60.0
    assert parse(None) == 50.0
    assert parse("") == 50.0
    for hostile in ['__import__("os").system("echo x")', "abc", True, "1e999999x"]:
        try:
            parse(hostile)
        except ValueError:
            continue
        raise AssertionError(f"_parse_frequency accepted {hostile!r}")


def check_no_eval_on_request_data() -> None:
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        source = fh.read()
    code_lines = [ln for ln in source.splitlines() if not ln.lstrip().startswith("#")]
    offenders = [ln for ln in code_lines if re.search(r"(?<![\w.])eval\(", ln)]
    assert not offenders, f"eval() still used on request data: {offenders}"


def check_index_responds(app_module) -> None:
    client = app_module.app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200, resp.status_code


def main() -> None:
    import app as app_module

    check_parse_frequency(app_module)
    check_no_eval_on_request_data()
    check_index_responds(app_module)
    print("request hardening checks passed")


if __name__ == "__main__":
    main()
