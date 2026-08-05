"""Open the desktop app by default, retaining the command-line test harness."""

import sys


if len(sys.argv) == 1:
    from .gui import main
else:
    from .cli import main


raise SystemExit(main())
