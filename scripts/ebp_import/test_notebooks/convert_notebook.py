import nbformat
from nbconvert import PythonExporter
import sys
import os

def convert_notebook(notebook_path, output_path=None):
    """
    Converts a Jupyter Notebook (.ipynb) to a clean Python script (.py) without cell markers,
    execution markers, or unnecessary extra lines.
    
    :param notebook_path: Path to the input .ipynb file
    :param output_path: Path to save the cleaned .py file (optional)
    """
    # Load the notebook
    with open(notebook_path, "r", encoding="utf-8") as f:
        notebook = nbformat.read(f, as_version=4)
    
    # Convert to Python script
    exporter = PythonExporter()
    script, _ = exporter.from_notebook_node(notebook)
    
    # Remove '# %%', '# In[8]:', 'Run Cell', 'Run Above', 'Debug Cell' markers and extra blank lines
    cleaned_script = []
    for line in script.split("\n"):
        if (not line.startswith("# %") and
            not line.startswith("# In[") and
            not "Run Cell" in line and
            not "Run Above" in line and
            not "Debug Cell" in line):
            cleaned_script.append(line)
    
    # Remove consecutive empty lines
    final_script = "\n".join([line for i, line in enumerate(cleaned_script) if i == 0 or line.strip() or cleaned_script[i-1].strip()])
    
    # Define output file path
    if output_path is None:
        output_path = os.path.join(os.path.dirname(notebook_path), "..", os.path.basename(notebook_path).replace(".ipynb", ".py"))

    
    # Save the cleaned script
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_script)
    
    print(f"Converted and cleaned script saved as: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_notebook.py <notebook_path> [output_path]")
    else:
        notebook_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        convert_notebook(notebook_file, output_file)