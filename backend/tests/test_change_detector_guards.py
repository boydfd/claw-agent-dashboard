"""Tests for change_detector file size and binary extension guards."""
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

os.environ["AGENTS_DIR"] = "/tmp/test-agents"
os.environ["DATA_DIR"] = "/tmp/test-data"

from backend.app import config as cfg

cfg.AGENTS_DIR = "/tmp/test-agents"
cfg.DATA_DIR = "/tmp/test-data"
cfg.BLUEPRINTS_DIR = os.path.join(cfg.AGENTS_DIR, "blueprints")

from backend.app.services import version_db
from backend.app.services.change_detector import (
    BINARY_EXTENSIONS,
    _should_skip_file,
)


@pytest_asyncio.fixture(autouse=True)
async def fresh_db(tmp_path):
    db_path = tmp_path / "versions.db"
    version_db.DB_PATH = db_path
    version_db._db = None
    await version_db.init_db()
    yield
    await version_db.close_db()


def test_binary_extensions_includes_tar():
    assert ".tar" in BINARY_EXTENSIONS
    assert ".gz" in BINARY_EXTENSIONS
    assert ".png" in BINARY_EXTENSIONS


def test_binary_extensions_excludes_svg():
    assert ".svg" not in BINARY_EXTENSIONS


def test_should_skip_binary_extension(tmp_path):
    f = tmp_path / "archive.tar"
    f.write_bytes(b"\x00" * 100)
    assert _should_skip_file(f) is True


def test_should_skip_large_file(tmp_path):
    f = tmp_path / "huge.md"
    f.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
    assert _should_skip_file(f) is True


def test_should_not_skip_normal_file(tmp_path):
    f = tmp_path / "normal.md"
    f.write_text("hello world")
    assert _should_skip_file(f) is False


def test_should_not_skip_svg(tmp_path):
    f = tmp_path / "icon.svg"
    f.write_text("<svg></svg>")
    assert _should_skip_file(f) is False


def test_should_skip_nonexistent_file(tmp_path):
    f = tmp_path / "gone.md"
    assert _should_skip_file(f) is True


@pytest.mark.asyncio
async def test_create_version_rejects_oversized_content():
    agent_id = await version_db.get_or_create_agent("workspace-test")
    oversized = "x" * (5 * 1024 * 1024 + 1)
    result = await version_db.create_version(
        agent_id=agent_id, file_path="big.md",
        content=oversized, content_hash="abc123",
        source="test",
    )
    assert result is None


@pytest.mark.asyncio
async def test_create_version_accepts_normal_content():
    agent_id = await version_db.get_or_create_agent("workspace-test")
    result = await version_db.create_version(
        agent_id=agent_id, file_path="ok.md",
        content="hello", content_hash=version_db.compute_hash("hello"),
        source="test",
    )
    assert result is not None
    assert result["file_path"] == "ok.md"
