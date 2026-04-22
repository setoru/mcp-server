from __future__ import annotations

from pathlib import Path

# Centralized defaults used by the standalone Huawei Cloud scripts in this folder.
#
# If you want to change the default scope file name/location, do it here once.

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCOPE_PATH = REPO_ROOT / ".opencode" / "huawei-scope-2.yaml"

