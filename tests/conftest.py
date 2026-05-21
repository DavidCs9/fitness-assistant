import sys
import os

# Make the shared layer importable without installing it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "shared", "python"))
