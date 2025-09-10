import csv
import subprocess
import sys
from pathlib import Path

from tools.rules_inventory import build_inventory


def test_rules_inventory_script(tmp_path):
    subprocess.check_call([sys.executable, "tools/rules_inventory.py"])
    csv_path = Path("docs/rules_inventory.csv")
    assert csv_path.exists()
    with csv_path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == len(build_inventory())
