import json
import subprocess
import sys
import tempfile


def test_installed_package_metadata_matches_module_version() -> None:
    script = """
import json
from importlib.metadata import version
import daily_stock_briefing

print(json.dumps({
    "module_version": daily_stock_briefing.__version__,
    "distribution_version": version("daily-stock-briefing"),
}))
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            check=True,
            cwd=temp_dir,
            text=True,
        )

    payload = json.loads(result.stdout)
    assert payload["module_version"] == payload["distribution_version"]
