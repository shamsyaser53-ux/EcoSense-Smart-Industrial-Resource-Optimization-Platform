import sys
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "ecosense_audit_report.txt"
SKIP = {".venv", "venv", "__pycache__", ".git", "node_modules"}

results = []

def add(title, output, code=0):
    status = "PASS" if code == 0 else "CHECK"
    results.append(f"\n{'=' * 60}\n{title}\nStatus: {status}\n{output}\n")

def run_command(title, command):
    try:
        p = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180
        )
        output = (p.stdout or "") + (p.stderr or "")
        add(title, output.strip() or "Command completed with no output.",
            p.returncode)
    except Exception as e:
        add(title, str(e), 1)

print("EcoSense audit started...")

# 1. Project files inventory
files = [
    str(p.relative_to(ROOT))
    for p in ROOT.rglob("*")
    if p.is_file()
    and not any(part in SKIP for part in p.parts)
    and REPORT.name != p.name
]
add("PROJECT FILES", "\n".join(sorted(files)) or "No files found.")

# 2. Check Python syntax without running application code
python_files = [
    p for p in ROOT.rglob("*.py")
    if not any(part in SKIP for part in p.parts)
]
syntax_errors = []
for path in python_files:
    try:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    except Exception as e:
        syntax_errors.append(f"{path.relative_to(ROOT)}: {e}")

add(
    "PYTHON SYNTAX",
    "\n".join(syntax_errors) if syntax_errors else
    f"All {len(python_files)} Python files compiled successfully.",
    1 if syntax_errors else 0
)

# 3. Dependency consistency
run_command("DEPENDENCY CHECK", [sys.executable, "-m", "pip", "check"])

# 4. Existing automated tests
tests_dir = ROOT / "tests"
if tests_dir.exists():
    run_command("AUTOMATED TESTS", [
        sys.executable, "-m", "pytest", "-v", "--tb=short"
    ])
else:
    add("AUTOMATED TESTS", "No tests/ folder found.", 1)

# 5. Try importing the FastAPI application and list routes
route_code = (
    "from main import app; "
    "print('Application title:', app.title); "
    "print('Application version:', app.version); "
    "print('Routes:'); "
    "[print(','.join(sorted(r.methods or [])), r.path) "
    "for r in app.routes if hasattr(r, 'methods')]"
)
run_command("APPLICATION IMPORT AND API ROUTES", [
    sys.executable, "-c", route_code
])

# 6. Check whether Git is available and report its status
if (ROOT / ".git").exists():
    run_command("GIT STATUS", ["git", "status", "--short"])
else:
    add("GIT STATUS", "No .git folder found; Git status skipped.")

# 7. Save a single report
header = (
    "ECOSENSE PROJECT AUDIT\n"
    f"Date: {datetime.now().isoformat(timespec='seconds')}\n"
    f"Project: {ROOT}\n"
    f"Python: {sys.version}\n"
)
report_text = header + "\n".join(results)
REPORT.write_text(report_text, encoding="utf-8")

print("\nAudit finished.")
print("Report saved to:", REPORT)
print("\nOpen ecosense_audit_report.txt and send me its contents.")