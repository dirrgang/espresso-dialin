"""Run Pyright against Python sources and the historical-analysis notebook."""

import subprocess
import sys

from pyright import cli

if __name__ == "__main__":
    source_status = cli.main(["--pythonpath", sys.executable, *sys.argv[1:]])
    notebook = "notebooks/01_historical_exploration.ipynb"
    notebook_status = subprocess.run(
        [sys.executable, "-m", "nbqa", "pyright", notebook, "--pythonpath", sys.executable],
        check=False,
    ).returncode
    raise SystemExit(source_status or notebook_status)
