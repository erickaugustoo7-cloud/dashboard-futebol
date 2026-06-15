# -*- coding: utf-8 -*-
"""
Script to export a fully‑self‑contained Colab notebook that runs the
prediction pipeline automatically, without any manual steps.

The notebook:
1. Installs required Python packages.
2. Loads the `GEMINI_API_KEY` from `.env.local` (if present).
3. Embeds the entire `generate_predictions.py` source.
4. Calls the `main()` function to produce predictions.
5. Saves the notebook as `football_predictor_colab.ipynb` in the project root.
"""

import os
import json
import nbformat
from nbformat.v4 import new_notebook, new_code_cell
from pathlib import Path

# Paths – project root is two levels up from this script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_NOTEBOOK = PROJECT_ROOT / "football_predictor_colab.ipynb"
GENERATE_SCRIPT = PROJECT_ROOT / "scripts" / "generate_predictions.py"
ENV_FILE = PROJECT_ROOT / ".env.local"

def load_env_vars():
    """Read env vars from `.env.local` if it exists.
    Returns a dict with the keys.
    """
    env_vars = {}
    if not ENV_FILE.is_file():
        return env_vars
    for line in ENV_FILE.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()
    return env_vars

def create_notebook():
    nb = new_notebook()
    # Cell 1 - install dependencies
    nb.cells.append(new_code_cell(
        """# Install required packages\n!pip install -q tensorflow groq pandas scikit-learn nbformat supabase"""
    ))
    # Cell 2 - set env vars in the runtime environment
    env_vars = load_env_vars()
    env_setup = "import os\n"
    keys_to_export = ["GROQ_API_KEY", "NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_ANON_KEY"]
    for key in keys_to_export:
        val = env_vars.get(key)
        if val:
            env_setup += f"os.environ['{key}'] = '{val}'\n"
    nb.cells.append(new_code_cell(env_setup))
    
    # Cell 3 - embed supabase_client.py and write to disk
    supabase_script = PROJECT_ROOT / "scripts" / "supabase_client.py"
    if supabase_script.is_file():
        nb.cells.append(new_code_cell(f"%%writefile supabase_client.py\n" + supabase_script.read_text(encoding="utf-8")))
    
    # Cell 4 - embed the full source of generate_predictions.py
    if not GENERATE_SCRIPT.is_file():
        raise FileNotFoundError(f"generate_predictions.py not found at {GENERATE_SCRIPT}")
    script_source = GENERATE_SCRIPT.read_text(encoding="utf-8")
    nb.cells.append(new_code_cell(script_source))
    
    # Cell 5 - execute the pipeline
    nb.cells.append(new_code_cell("""if __name__ == '__main__':\n    main()\n"""))
    
    # Write the notebook file
    with open(EXPORT_NOTEBOOK, 'w', encoding='utf-8') as f:
        nbformat.write(nb, f)

    print(f"Notebook generated successfully at {EXPORT_NOTEBOOK}")

if __name__ == "__main__":
    create_notebook()
