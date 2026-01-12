from __future__ import annotations

import sys


def _entrypoint() -> int:
    from . import cli

    cli.main()
    return 0


if __name__ == "__main__":
    sys.exit(_entrypoint())
