"""Execute the WRDS notebook and verify every cell. No fixture performance mode."""
from pathlib import Path
import nbformat
from nbclient import NotebookClient

root=Path(__file__).resolve().parent
path=root/'01_cost_of_customization.ipynb'
nb=nbformat.read(path,as_version=4)
NotebookClient(nb,timeout=1800,kernel_name='python3',resources={'metadata':{'path':str(root)}}).execute()
code_cells=[c for c in nb.cells if c.cell_type=='code']
assert all(c.execution_count is not None for c in code_cells)
assert not any(o.output_type=='error' for c in code_cells for o in c.outputs)
nbformat.write(nb,path)
print(f'Executed all {len(code_cells)} WRDS notebook code cells without errors.')
