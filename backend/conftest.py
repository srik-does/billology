import sys
from pathlib import Path

# Ensure `backend/` is importable as the project root so `import src...` works
# regardless of where pytest is invoked from.
sys.path.insert(0, str(Path(__file__).parent))
