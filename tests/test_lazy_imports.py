import json
import subprocess
import sys


def test_import_mem0_does_not_import_qdrant_client():
    """Importing mem0 must not construct the default MemoryConfig.

    Memory.__init__'s config default used to be evaluated at import time,
    which pulled in the default vector store's SDK (qdrant_client) for every
    consumer, whatever their configured provider. The probe runs in a
    subprocess so it sees exactly what `import mem0` loads.
    """
    probe = (
        "import json, sys\n"
        "import mem0\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.startswith('qdrant'))))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    assert json.loads(result.stdout) == []
