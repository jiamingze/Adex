import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("test_stack.py")), run_name="__main__")
