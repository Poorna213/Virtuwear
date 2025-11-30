# diagnose_imports.py
import sys
import os
import importlib
import pkgutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def try_import(name):
    try:
        m = importlib.import_module(name)
        loc = getattr(m, "__file__", "built-in/module-without-file")
        version = getattr(m, "__version__", None)
        print(f"[OK]  import {name:25} from {loc}    version={version}")
        return True
    except Exception as e:
        print(f"[FAIL] import {name:25} -> {e.__class__.__name__}: {e}")
        return False

def print_sysinfo():
    print("=== Python executable ===")
    print(sys.executable)
    print("=== sys.path (first 10 entries) ===")
    for i,p in enumerate(sys.path[:20]):
        print(f"{i:02d}: {p}")
    print()

def print_tree(root: Path, depth=2):
    print(f"=== Directory tree under {root} (depth={depth}) ===")
    def _walk(p, curdepth):
        if curdepth > depth: 
            return
        for child in sorted(p.iterdir()):
            prefix = "  " * curdepth + ("└─ " if curdepth>0 else "")
            print(prefix + child.name)
            if child.is_dir():
                _walk(child, curdepth+1)
    _walk(root, 0)
    print()

def check_tryondiffusion_paths():
    td_name = "tryondiffusion"
    print(f"=== Searching for local '{td_name}' folder(s) under project root ===")
    found = list(ROOT.rglob(td_name))
    for f in found:
        print(" -", f)
    if not found:
        print(" (none found)")

if __name__ == "__main__":
    print_sysinfo()
    print_tree(ROOT, depth=2)
    check_tryondiffusion_paths()

    print("=== Attempting imports ===")
    # standard libs/frameworks
    for pkg in ["torch", "diffusers", "PIL", "PIL.Image", "flask", "flask_cors", "numpy"]:
        try_import(pkg)
    # try your local tryondiffusion package variants
    local_candidates = [
        "tryondiffusion",
        "tryondiffusion.run_inference",
        "tryondiffusion.inference",
        "tryondiffusion.tron",
        "tryondiffusion.modules",
        "tryondiffusion.tryon",
        "modules.tryondiffusion",
        "modules.tryon",
        "run_inference",
        "inference",
        "tryon"
    ]
    print()
    print("=== Trying local repo import candidates ===")
    for c in local_candidates:
        try_import(c)

    print()
    print("=== How to fix common issues ===")
    print("1) If imports of the local 'tryondiffusion' package fail, ensure the folder containing it is on sys.path.")
    print("   Example: add these lines at the top of app.py (before other imports):")
    print("     import sys, os")
    print(f"     sys.path.insert(0, r'{ROOT / 'tryondiffusion'}')  # or the exact folder that contains the package __init__.py")
    print("2) Or run Python from project root (you already are).")
    print("3) If third-party imports fail, pip-install inside your venv, e.g.:")
    print("     pip install torch diffusers transformers xformers pillow flask flask-cors")
    print("4) Paste the output of this script here if you want further guidance.")
