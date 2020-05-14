import sys

from windows_upgrade import check_for_updates
from run import possibly_start_with_gui

if check_for_updates():
    input(
        "New version of windows_run.exe is required. Please run windows_upgrade.exe (press any key to continue)"
    )
    sys.exit(1)
else:
    possibly_start_with_gui()
