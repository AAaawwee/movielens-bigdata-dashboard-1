import hashlib
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".venv"
REQUIREMENTS = ROOT / "dashboard" / "requirements.txt"


def main():
    if sys.version_info < (3, 11):
        print("MovieLens requires Python 3.11 or newer.", file=sys.stderr)
        return 1

    python = ENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    stamp = ENV / ".dashboard-requirements"
    fingerprint = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    if not python.is_file():
        venv.create(ENV, with_pip=True)
    if not stamp.is_file() or stamp.read_text(encoding="ascii") != fingerprint:
        print("Installing the dashboard dependencies for the first run…", flush=True)
        subprocess.run([str(python), "-m", "pip", "--disable-pip-version-check", "install",
                        "-r", str(REQUIREMENTS)], check=True)
        stamp.write_text(fingerprint, encoding="ascii")

    return subprocess.call([str(python), str(ROOT / "dashboard" / "app.py"),
                            *sys.argv[1:], "--mode", "snapshot"], cwd=ROOT)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except (OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"MovieLens startup failed: {error}")
