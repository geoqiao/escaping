import sys

from escaping.cli import run_cli

if __name__ == "__main__":
    try:
        run_cli()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        sys.exit(1)
