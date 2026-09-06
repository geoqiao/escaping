"""Map a step-scoped token, then run the installed console with the original Config."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from escaping.config import PathsConfig, read_config_overrides, security_from_config
from escaping.output_safety import validate_output_containment


def compiler_env(name: str, token: str, inherited: Mapping[str, str]) -> dict[str, str]:
    # Identifier syntax is validated by the generator's security_from_config seam.
    control = name.upper()
    if name != "GITHUB_TOKEN" and (
        any(key.upper() == control for key in inherited)
        or control
        in {
            "PATH",
            "HOME",
            "USER",
            "LOGNAME",
            "PWD",
            "OLDPWD",
            "ENV",
            "IFS",
            "CDPATH",
            "PS4",
            "PROMPT_COMMAND",
            "VIRTUAL_ENV",
            "COMPILER_TOKEN",
            "PLATFORM_TOKEN",
            "LABEL_TOKEN",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
            "REQUESTS_CA_BUNDLE",
            "CURL_CA_BUNDLE",
        }
        or control.startswith(
            (
                "PYTHON",
                "LD_",
                "DYLD_",
                "SSL",
                "OPENSSL_",
                "GIT",
                "GH_",
                "UV_",
                "BASH",
                "SHELL",
                "ZSH",
                "ZDOTDIR",
                "RUNNER_",
                "ACTIONS_",
                "INPUT_",
                "NODE_",
                "CONDA_",
            )
        )
    ):
        raise ValueError("token_env collides with process/platform controls")
    env = {
        k: v
        for k, v in inherited.items()
        if k.upper()
        not in {
            "COMPILER_TOKEN",
            "PLATFORM_TOKEN",
            "LABEL_TOKEN",
            "GH_TOKEN",
            "GITHUB_TOKEN",
        }
    }
    env[name] = token
    return env


def main() -> None:
    config = Path(sys.argv[1]).expanduser().absolute()
    context = Path(sys.argv[2]).absolute()
    # Do not resolve Settings/Profile/Issues here: the installed CLI owns that work.
    overrides = read_config_overrides(config)
    security = security_from_config(overrides)
    paths = PathsConfig.model_validate(overrides.get("paths", {}))
    output = validate_output_containment(paths.output, config.parent)
    if any(c in str(output) for c in "\r\n\x00"):
        raise ValueError("output cannot be represented as a workflow output")
    token = os.environ["COMPILER_TOKEN"]
    if not token:
        raise ValueError("missing compiler token")
    env = compiler_env(security.token_env, token, os.environ)
    console = Path(sys.executable).absolute().parent / (
        "escpe.exe" if sys.platform == "win32" else "escpe"
    )
    subprocess.run(  # noqa: S603 - absolute installed console, separate arguments, no shell
        [str(console), "--config", str(config), "--context", str(context)],
        env=env,
        check=True,
    )
    # Only successful CLI publication can expose a path to the upload step.
    validate_output_containment(paths.output, config.parent)
    if destination := os.environ.get("GITHUB_OUTPUT"):
        with Path(destination).open("a", encoding="utf-8") as stream:
            stream.write("output=" + str(output) + "\n")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError:
        sys.exit(
            1
        )  # The console already emitted safe diagnostics; do not echo argv/env.
    except Exception:
        print(
            "Site build stopped; check Config, context, token mapping and output path.",
            file=sys.stderr,
        )
        sys.exit(1)
