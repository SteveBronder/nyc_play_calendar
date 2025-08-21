import pathlib
import sys

# Ensure the src directory is on the path for tests without installing the package
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
