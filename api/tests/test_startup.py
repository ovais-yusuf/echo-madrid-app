"""Exercise the actual container startup script without a real database/server."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("port", [None, "10000"])
def test_startup_migrates_before_server_and_respects_port(tmp_path, port):
    result, calls = run_script(tmp_path, port=port)
    assert result.returncode == 0
    assert calls == ["-m alembic upgrade head", f"-m uvicorn app.main:app --host 0.0.0.0 --port {port or '8000'}"]


def test_failed_migration_prevents_server_start(tmp_path):
    result, calls = run_script(tmp_path, migration_exit="7")
    assert result.returncode == 7
    assert calls == ["-m alembic upgrade head"]


def run_script(tmp_path, *, port=None, migration_exit="0"):
    api_dir = tmp_path / "api"
    api_dir.mkdir()
    shutil.copyfile(Path(__file__).resolve().parents[1] / "start.sh", api_dir / "start.sh")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_python = bin_dir / "python"
    fake_python.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$CALL_LOG"
[ "$PWD" = "$EXPECTED_CWD" ] || exit 99
if [ "$2" = alembic ]; then exit "$MIGRATION_EXIT"; fi
''')
    fake_python.chmod(0o755)
    log = tmp_path / "calls"
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
           "CALL_LOG": str(log), "EXPECTED_CWD": str(api_dir), "MIGRATION_EXIT": migration_exit}
    env.pop("PORT", None)
    if port is not None:
        env["PORT"] = port
    result = subprocess.run(["sh", str(api_dir / "start.sh")], cwd=tmp_path, env=env,
                            capture_output=True, text=True)
    return result, log.read_text().splitlines()
