#!/usr/bin/env bash
# Native uv installation of the one verified generator checkout. No token is needed.
set -euo pipefail
source=$(cd "${1:?generator source directory required}" && pwd -P)
commit=${2:?resolved full commit SHA required}
python=${3:?explicit Python version or executable required}

if [[ ! "$commit" =~ ^[0-9a-f]{40}$ ]] || [[ "$(git -C "$source" rev-parse HEAD)" != "$commit" ]]; then
  echo "Generator checkout does not match the resolved commit; stop." >&2
  exit 1
fi
git -C "$source" diff --exit-code HEAD --quiet
if [[ "${UV_PROJECT_ENVIRONMENT:-}" != /* ]] || [[ -e "$UV_PROJECT_ENVIRONMENT" || -L "$UV_PROJECT_ENVIRONMENT" ]] || [[ "$UV_PROJECT_ENVIRONMENT/" == "$source/"* ]]; then
  echo "Set UV_PROJECT_ENVIRONMENT to a fresh absolute environment outside the source." >&2
  exit 1
fi
uv sync --project "$source" --python "$python" \
  --locked --no-default-groups --group build --no-editable \
  --no-build-isolation-package escpe
git -C "$source" diff --exit-code HEAD --quiet
uv --version
"$UV_PROJECT_ENVIRONMENT/bin/python" -I - "$source" "$commit" <<'PY'
import hashlib
import importlib.metadata as metadata
import json
import sys
import tomllib
from pathlib import Path
import escaping

source = Path(sys.argv[1])
distribution = metadata.distribution("escpe")
if not Path(escaping.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
    raise SystemExit("Generator import is outside the installed environment")
if json.loads(distribution.read_text("direct_url.json"))["dir_info"].get("editable"):
    raise SystemExit("Generator must not be installed editable")
print(json.dumps({
    "commit": sys.argv[2],
    "python": sys.version,
    "lock_sha256": hashlib.sha256((source / "uv.lock").read_bytes()).hexdigest(),
    "pyproject_sha256": hashlib.sha256((source / "pyproject.toml").read_bytes()).hexdigest(),
    "build_system": tomllib.loads((source / "pyproject.toml").read_text())["build-system"],
    "wheel": distribution.read_text("WHEEL"),
    "installed": {d.metadata["Name"]: d.version for d in metadata.distributions()},
}, sort_keys=True))
PY
