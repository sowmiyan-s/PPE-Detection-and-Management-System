"""
Test suite for dynamic database engine switching between SQL engines (SQLite and PostgreSQL).
"""

import os
import pytest
from src.core import config
from src.core import db


def test_config_db_engine_default():
    """Verify default database engine setting."""
    engine = db.get_db_engine()
    assert engine in ("sqlite", "postgresql", "rdbms")


def test_set_db_engine_sqlite():
    """Verify switching to SQLite engine."""
    original_engine = db.get_db_engine()
    try:
        new_engine = db.set_db_engine("sqlite")
        assert new_engine == "sqlite"
        assert db.get_db_engine() == "sqlite"
        assert db.is_rdbms_active() is True
    finally:
        db.set_db_engine(original_engine)


def test_set_db_engine_rdbms():
    """Verify switching to PostgreSQL / RDBMS engine."""
    original_engine = db.get_db_engine()
    try:
        new_engine = db.set_db_engine("postgresql")
        assert new_engine == "postgresql"
        assert db.get_db_engine() == "postgresql"
        assert db.is_rdbms_active() is True

        new_engine2 = db.set_db_engine("rdbms")
        assert new_engine2 == "postgresql"
        assert db.is_rdbms_active() is True
    finally:
        db.set_db_engine(original_engine)


@pytest.mark.asyncio
async def test_get_cameras_with_sql():
    """Verify camera access remains safe and non-blocking under SQL mode."""
    original_engine = db.get_db_engine()
    try:
        db.set_db_engine("sqlite")
        cameras = await db.get_cameras()
        assert isinstance(cameras, list)
    finally:
        db.set_db_engine(original_engine)


@pytest.mark.asyncio
async def test_sync_databases_reconciliation():
    """Verify sync_databases returns status and reconciled counts."""
    status = db.get_db_status()
    assert "engine" in status

    sync_res = await db.sync_databases()
    assert sync_res["success"] is True
    assert "synced_counts" in sync_res
