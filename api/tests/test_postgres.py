"""Real PostgreSQL migration and worker-lock test. Disposable database only.

CI provisions a separate postgres:16 service; never uses DATABASE_URL from a developer.
"""
import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='Disposable PostgreSQL not available')
def test_migrations_and_cross_connection_lock(monkeypatch):
    from pipeline import worker
    url = os.environ['TEST_POSTGRES_URL']
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, 'DATABASE_URL': url, 'PYTHONPATH': str(root/'api')}
    subprocess.run(['alembic','upgrade','head'],cwd=root/'api',env=env,check=True,capture_output=True)
    engine=create_engine(url)
    monkeypatch.setattr(worker,'engine',engine)
    # Second connection must skip all upstream work while the first owns the lock.
    with engine.connect() as lock:
        lock.execute(text('SELECT pg_advisory_lock(:key)'), {'key':worker.LOCK_ID}); lock.commit()
        assert worker.run_once()[0].status=='skipped'
        lock.execute(text('SELECT pg_advisory_unlock(:key)'), {'key':worker.LOCK_ID}); lock.commit()
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version"))=='c9e20261111'
        assert conn.scalar(text("SELECT COUNT(*) FROM standings_snapshot"))==0
    subprocess.run(['alembic','downgrade','b88b48e25165'],cwd=root/'api',env=env,check=True,capture_output=True)
    subprocess.run(['alembic','upgrade','head'],cwd=root/'api',env=env,check=True,capture_output=True)
    engine.dispose()
