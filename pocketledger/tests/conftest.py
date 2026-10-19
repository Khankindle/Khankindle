import sys
from pathlib import Path

# Make the pocketledger modules importable when running `pytest` from pocketledger/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
