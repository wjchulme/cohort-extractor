"""This script generates a pyinstaller invocation that includes every
package currently installed.

The reason is so we can provide Windows users a single
python+requirements binary so they don't need to learn about pip or
virtualenvs.

"""
import subprocess
import itertools
import pkg_resources

packages = list(pkg_resources.working_set)

import_args = list(
    itertools.chain(
        *zip(["--hidden-import"] * len(packages), [p.project_name for p in packages])
    )
)

other_args = ["--paths=.", "--onefile", "--add-data", "runner/VERSION;runner"]
run_cmd = (
    ["pyinstaller"] + import_args + other_args + ["runner/windows_run.py",]
)
subprocess.run(run_cmd, check=True)

# This should make it smaller
upgrade_cmd = (
    ["pyinstaller"] + other_args + ["runner/windows_upgrade.py",]
)

subprocess.run(upgrade_cmd, check=True)
