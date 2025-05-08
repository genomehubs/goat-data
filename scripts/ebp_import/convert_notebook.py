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

def convert_py_to_notebook(py_path, output_path=None):
    """
    Converts a Python script (.py) to a Jupyter Notebook (.ipynb).
    The script will be split into cells based on empty lines.
    
    :param py_path: Path to the input .py file
    :param output_path: Path to save the .ipynb file (optional)
    """
    # Read the Python file
    with open(py_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Split the content into cells based on empty lines
    cells = []
    current_cell = []
    
    for line in content.split("\n"):
        if line.strip() == "":
            if current_cell:  # Only create a new cell if we have content
                cells.append("\n".join(current_cell))
                current_cell = []
        else:
            current_cell.append(line)
    
    # Add the last cell if it exists
    if current_cell:
        cells.append("\n".join(current_cell))
    
    # Create a new notebook
    notebook = nbformat.v4.new_notebook()
    
    # Add cells to the notebook
    for cell_content in cells:
        notebook.cells.append(nbformat.v4.new_code_cell(cell_content))
    
    # Define output file path
    if output_path is None:
        output_path = os.path.join(os.path.dirname(py_path), os.path.basename(py_path).replace(".py", ".ipynb"))
    
    # Save the notebook
    with open(output_path, "w", encoding="utf-8") as f:
        nbformat.write(notebook, f)
    
    print(f"Converted Python script to notebook saved as: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_notebook.py <input_file> [output_file]")
        print("The script will automatically detect the file type and convert accordingly.")
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        
        if input_file.endswith(".ipynb"):
            convert_notebook(input_file, output_file)
        elif input_file.endswith(".py"):
            convert_py_to_notebook(input_file, output_file)
        else:
            print("Error: Input file must be either .ipynb or .py")