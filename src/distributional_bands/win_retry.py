"""Run a module with os.replace retried on transient Windows file locks.

Antivirus scanners, search indexers or editor file watchers can briefly hold a
checkpoint that was just written; os.replace then fails with PermissionError
(WinError 5 or 32). Retrying keeps the write-temp-then-replace atomic semantics.
This launcher is outside every run signature, so existing checkpoints stay valid.

Usage: python -m distributional_bands.win_retry <module> [module arguments...]
"""

from __future__ import annotations

import os
import runpy
import sys
import time

ATTEMPTS = 20
DELAY_SECONDS = 0.25

_replace = os.replace


def retrying_replace(source, target, **kwargs):
    """os.replace with linear back-off (about 50 s in total) on PermissionError."""
    for attempt in range(ATTEMPTS):
        try:
            return _replace(source, target, **kwargs)
        except PermissionError:
            if attempt == ATTEMPTS - 1:
                raise
            time.sleep(DELAY_SECONDS * (attempt + 1))


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    module = sys.argv[1]
    sys.argv = [module] + sys.argv[2:]
    os.replace = retrying_replace
    runpy.run_module(module, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
