"""Execute the notebook from a fresh kernel, optionally using offline fixtures."""
import argparse
from pathlib import Path
import nbformat
from nbclient import NotebookClient

parser = argparse.ArgumentParser()
parser.add_argument("--synthetic", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parent
path = root / "01_cost_of_customization.ipynb"
nb = nbformat.read(path, as_version=4)
if args.synthetic:
    for cell in nb.cells:
        if cell.cell_type == "code":
            cell.source = cell.source.replace('DATA_MODE = "market"', 'DATA_MODE = "synthetic"')
NotebookClient(nb, timeout=240, kernel_name="python3",
               resources={"metadata": {"path": str(root)}}).execute()
code_cells = [c for c in nb.cells if c.cell_type == "code"]
assert all(c.execution_count is not None for c in code_cells)
assert not any(o.output_type == "error" for c in code_cells for o in c.outputs)
if not args.synthetic:
    nbformat.write(nb, path)
print(f"Executed {len(code_cells)} code cells successfully ({'synthetic' if args.synthetic else 'market'}).")
