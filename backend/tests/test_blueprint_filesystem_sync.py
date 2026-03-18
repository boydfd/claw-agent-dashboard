"""Tests for blueprint filesystem sync — pending changes CRUD and accept/reject."""
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# Patch config before importing services
os.environ["AGENTS_DIR"] = "/tmp/test-agents"
os.environ["DATA_DIR"] = "/tmp/test-data"

from backend.app import config as cfg

cfg.AGENTS_DIR = "/tmp/test-agents"
cfg.DATA_DIR = "/tmp/test-data"
cfg.BLUEPRINTS_DIR = os.path.join(cfg.AGENTS_DIR, "blueprints")

from backend.app.services import version_db


@pytest_asyncio.fixture(autouse=True)
async def fresh_db(tmp_path):
    """Create a fresh database for each test."""
    db_path = tmp_path / "versions.db"
    version_db.DB_PATH = db_path
    version_db._db = None
    await version_db.init_db()
    yield
    await version_db.close_db()


@pytest_asyncio.fixture
async def blueprint():
    """Create a test blueprint with a virtual agent."""
    agent_id = await version_db.get_or_create_virtual_agent("_blueprint-test")
    bp = await version_db.create_blueprint(
        name="test", description="Test blueprint", agent_id=agent_id
    )
    # Add a template file
    await version_db.create_template(agent_id, "SOUL.md", "# Original content")
    return bp


class TestPendingChangesCRUD:
    @pytest.mark.asyncio
    async def test_upsert_creates_pending_change(self, blueprint):
        result = await version_db.upsert_pending_change(
            blueprint_id=blueprint["id"],
            file_path="SOUL.md",
            change_type="modified",
            old_content="# Original content",
            new_content="# Modified content",
            old_hash=version_db.compute_hash("# Original content"),
            new_hash=version_db.compute_hash("# Modified content"),
        )
        assert result["status"] == "pending"
        assert result["change_type"] == "modified"
        assert result["file_path"] == "SOUL.md"

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_pending_change(self, blueprint):
        await version_db.upsert_pending_change(
            blueprint_id=blueprint["id"], file_path="SOUL.md",
            change_type="modified", old_content="old", new_content="new1",
            old_hash="h1", new_hash="h2",
        )
        result = await version_db.upsert_pending_change(
            blueprint_id=blueprint["id"], file_path="SOUL.md",
            change_type="modified", old_content="old", new_content="new2",
            old_hash="h1", new_hash="h3",
        )
        changes = await version_db.list_pending_changes(blueprint["id"])
        assert len(changes) == 1
        assert changes[0]["new_content"] == "new2"

    @pytest.mark.asyncio
    async def test_list_pending_changes_filters_by_blueprint(self, blueprint):
        await version_db.upsert_pending_change(
            blueprint_id=blueprint["id"], file_path="SOUL.md",
            change_type="modified", old_content="a", new_content="b",
            old_hash="h1", new_hash="h2",
        )
        changes = await version_db.list_pending_changes(blueprint["id"])
        assert len(changes) == 1
        all_changes = await version_db.list_pending_changes()
        assert len(all_changes) == 1

    @pytest.mark.asyncio
    async def test_get_pending_changes_summary(self, blueprint):
        await version_db.upsert_pending_change(
            blueprint_id=blueprint["id"], file_path="SOUL.md",
            change_type="modified", old_content="a", new_content="b",
            old_hash="h1", new_hash="h2",
        )
        await version_db.upsert_pending_change(
            blueprint_id=blueprint["id"], file_path="TOOLS.md",
            change_type="added", old_content=None, new_content="new",
            old_hash=None, new_hash="h3",
        )
        summary = await version_db.get_pending_changes_summary()
        assert len(summary) == 1
        assert summary[0]["pending_count"] == 2
        assert summary[0]["blueprint_name"] == "test"

    @pytest.mark.asyncio
    async def test_resolve_pending_change(self, blueprint):
        pc = await version_db.upsert_pending_change(
            blueprint_id=blueprint["id"], file_path="SOUL.md",
            change_type="modified", old_content="a", new_content="b",
            old_hash="h1", new_hash="h2",
        )
        result = await version_db.resolve_pending_change(pc["id"], "accepted")
        assert result is True
        changes = await version_db.list_pending_changes(blueprint["id"])
        assert len(changes) == 0

    @pytest.mark.asyncio
    async def test_delete_pending_change_by_file(self, blueprint):
        await version_db.upsert_pending_change(
            blueprint_id=blueprint["id"], file_path="SOUL.md",
            change_type="modified", old_content="a", new_content="b",
            old_hash="h1", new_hash="h2",
        )
        deleted = await version_db.delete_pending_change_by_file(blueprint["id"], "SOUL.md")
        assert deleted is True
        changes = await version_db.list_pending_changes(blueprint["id"])
        assert len(changes) == 0


class TestBlueprintDiskInitialization:
    @pytest.mark.asyncio
    async def test_initialize_creates_dir_and_writes_files(self, blueprint, tmp_path):
        """DB has blueprint with template → should create dir + write file."""
        bp_dir = tmp_path / "blueprints"
        cfg.BLUEPRINTS_DIR = str(bp_dir)

        from backend.app.services import blueprint_service
        await blueprint_service.initialize_blueprint_dirs()

        assert (bp_dir / "test" / "SOUL.md").exists()
        content = (bp_dir / "test" / "SOUL.md").read_text()
        assert content == "# Original content"

    @pytest.mark.asyncio
    async def test_initialize_skips_unknown_disk_dirs(self, tmp_path):
        """Disk dir with no DB record → should be ignored."""
        bp_dir = tmp_path / "blueprints"
        (bp_dir / "unknown").mkdir(parents=True)
        (bp_dir / "unknown" / "SOUL.md").write_text("stuff")
        cfg.BLUEPRINTS_DIR = str(bp_dir)

        from backend.app.services import blueprint_service
        await blueprint_service.initialize_blueprint_dirs()
        # No error, unknown dir is simply left alone


class TestBlueprintScanning:
    @pytest_asyncio.fixture
    async def scanner_setup(self, blueprint, tmp_path):
        """Set up a blueprint dir with files for scanning."""
        bp_dir = tmp_path / "blueprints" / "test"
        bp_dir.mkdir(parents=True)
        (bp_dir / "SOUL.md").write_text("# Modified content")  # different from DB
        (bp_dir / "NEW.md").write_text("# New file")  # not in DB
        cfg.BLUEPRINTS_DIR = str(tmp_path / "blueprints")
        return bp_dir

    @pytest.mark.asyncio
    async def test_scan_detects_modified_file(self, scanner_setup, blueprint):
        from backend.app.services.change_detector import HashScanDetector
        detector = HashScanDetector()
        await detector._scan_blueprints()

        changes = await version_db.list_pending_changes(blueprint["id"])
        modified = [c for c in changes if c["change_type"] == "modified"]
        assert len(modified) == 1
        assert modified[0]["file_path"] == "SOUL.md"
        assert modified[0]["new_content"] == "# Modified content"

    @pytest.mark.asyncio
    async def test_scan_detects_added_file(self, scanner_setup, blueprint):
        from backend.app.services.change_detector import HashScanDetector
        detector = HashScanDetector()
        await detector._scan_blueprints()

        changes = await version_db.list_pending_changes(blueprint["id"])
        added = [c for c in changes if c["change_type"] == "added"]
        assert len(added) == 1
        assert added[0]["file_path"] == "NEW.md"

    @pytest.mark.asyncio
    async def test_scan_detects_deleted_file(self, blueprint, tmp_path):
        """DB has SOUL.md but disk dir is empty → should detect deletion."""
        bp_dir = tmp_path / "blueprints" / "test"
        bp_dir.mkdir(parents=True)
        # No SOUL.md on disk
        cfg.BLUEPRINTS_DIR = str(tmp_path / "blueprints")

        from backend.app.services.change_detector import HashScanDetector
        detector = HashScanDetector()
        await detector._scan_blueprints()

        changes = await version_db.list_pending_changes(blueprint["id"])
        deleted = [c for c in changes if c["change_type"] == "deleted"]
        assert len(deleted) == 1
        assert deleted[0]["file_path"] == "SOUL.md"

    @pytest.mark.asyncio
    async def test_scan_auto_clears_when_reverted(self, scanner_setup, blueprint):
        """File changed then changed back → pending change should be cleared."""
        from backend.app.services.change_detector import HashScanDetector
        detector = HashScanDetector()
        await detector._scan_blueprints()

        # Now revert the file to match DB
        bp_dir = Path(cfg.BLUEPRINTS_DIR) / "test"
        (bp_dir / "SOUL.md").write_text("# Original content")
        await detector._scan_blueprints()

        changes = await version_db.list_pending_changes(blueprint["id"])
        modified = [c for c in changes if c["file_path"] == "SOUL.md"]
        assert len(modified) == 0  # auto-cleared


class TestAcceptReject:
    @pytest_asyncio.fixture
    async def pending_change(self, blueprint, tmp_path):
        """Create a pending change with disk file."""
        bp_dir = tmp_path / "blueprints" / "test"
        bp_dir.mkdir(parents=True)
        (bp_dir / "SOUL.md").write_text("# Modified content")
        cfg.BLUEPRINTS_DIR = str(tmp_path / "blueprints")
        cfg.AGENTS_DIR = str(tmp_path / "agents")

        pc = await version_db.upsert_pending_change(
            blueprint_id=blueprint["id"], file_path="SOUL.md",
            change_type="modified",
            old_content="# Original content",
            new_content="# Modified content",
            old_hash=version_db.compute_hash("# Original content"),
            new_hash=version_db.compute_hash("# Modified content"),
        )
        return pc

    @pytest.mark.asyncio
    async def test_accept_updates_db_template(self, pending_change, blueprint):
        from backend.app.services import blueprint_service
        result = await blueprint_service.accept_pending_change(pending_change["id"])
        assert result["accepted"] is True

        # DB template should be updated
        template = await version_db.get_template_by_path(blueprint["agent_id"], "SOUL.md")
        assert template["content"] == "# Modified content"

    @pytest.mark.asyncio
    async def test_accept_creates_version_record(self, pending_change, blueprint):
        from backend.app.services import blueprint_service
        await blueprint_service.accept_pending_change(pending_change["id"])

        # Version should exist
        versions, total = await version_db.get_versions(blueprint["agent_id"], "SOUL.md")
        assert len(versions) >= 1
        latest = versions[0]
        assert latest["source"] == "filesystem_sync"

    @pytest.mark.asyncio
    async def test_reject_reverts_file_on_disk(self, pending_change, blueprint):
        from backend.app.services import blueprint_service
        await blueprint_service.reject_pending_change(pending_change["id"])

        bp_dir = Path(cfg.BLUEPRINTS_DIR) / "test"
        content = (bp_dir / "SOUL.md").read_text()
        assert content == "# Original content"

    @pytest.mark.asyncio
    async def test_reject_deletes_added_file(self, blueprint, tmp_path):
        bp_dir = tmp_path / "blueprints" / "test"
        bp_dir.mkdir(parents=True)
        (bp_dir / "NEW.md").write_text("# New file")
        cfg.BLUEPRINTS_DIR = str(tmp_path / "blueprints")

        pc = await version_db.upsert_pending_change(
            blueprint_id=blueprint["id"], file_path="NEW.md",
            change_type="added", old_content=None, new_content="# New file",
            old_hash=None, new_hash=version_db.compute_hash("# New file"),
        )
        from backend.app.services import blueprint_service
        await blueprint_service.reject_pending_change(pc["id"])

        assert not (bp_dir / "NEW.md").exists()
