"""Tests for blueprint import-from-agent functionality."""
import asyncio
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

# Patch config before importing services
_test_dir = tempfile.mkdtemp(prefix="bp-test-")
os.environ["AGENTS_DIR"] = os.path.join(_test_dir, "agents")
os.environ["DATA_DIR"] = os.path.join(_test_dir, "data")
os.environ["AGENTS_HOST_DIR"] = ""

import backend.app.config as cfg
cfg.AGENTS_DIR = os.path.join(_test_dir, "agents")
cfg.DATA_DIR = os.path.join(_test_dir, "data")
cfg.AGENTS_HOST_DIR = ""

from backend.app.services import version_db, file_service, blueprint_service
from backend.app.services.blueprint_service import _matches_exclude_pattern


@pytest_asyncio.fixture(autouse=True)
async def setup_db(tmp_path):
    """Initialize a fresh DB for each test."""
    db_path = tmp_path / "versions.db"
    version_db.DB_PATH = db_path
    # Reset connection
    if version_db._db is not None:
        await version_db._db.close()
        version_db._db = None
    await version_db.init_db()
    yield
    if version_db._db is not None:
        await version_db._db.close()
        version_db._db = None


@pytest.fixture
def agent_workspace(tmp_path):
    """Create a mock agent workspace with files."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    ws = agents_dir / "workspace-test-agent"
    ws.mkdir()

    # Patch AGENTS_DIR in both config and file_service (which imports it at module level)
    old_cfg_dir = cfg.AGENTS_DIR
    old_fs_dir = file_service.AGENTS_DIR
    cfg.AGENTS_DIR = str(agents_dir)
    file_service.AGENTS_DIR = str(agents_dir)

    # Create files
    (ws / "CLAUDE.md").write_text("# Agent: !{AGENT_NAME}\nProject: !{PROJECT}")
    (ws / "SOUL.md").write_text("You are !{AGENT_NAME}.")
    (ws / "config.json").write_text('{"name": "!{AGENT_NAME}"}')

    # Skills
    (ws / "skills" / "greeting").mkdir(parents=True)
    (ws / "skills" / "greeting" / "SKILL.md").write_text("name: greeting\nstyle: !{GREETING_STYLE}")

    # Memory (to be excluded)
    (ws / "memories").mkdir()
    (ws / "memories" / "session.md").write_text("memory content")

    # Logs (to be excluded)
    (ws / "logs").mkdir()
    (ws / "logs" / "debug.log").write_text("log content")

    yield {"agents_dir": agents_dir, "workspace": ws, "name": "workspace-test-agent"}

    cfg.AGENTS_DIR = old_cfg_dir
    file_service.AGENTS_DIR = old_fs_dir


# --- Tests for _matches_exclude_pattern ---

class TestMatchesExcludePattern:

    def test_basename_pattern_matches_any_depth(self):
        assert _matches_exclude_pattern("foo.md", ["*.md"]) is True
        assert _matches_exclude_pattern("sub/foo.md", ["*.md"]) is True
        assert _matches_exclude_pattern("a/b/c.md", ["*.md"]) is True

    def test_basename_pattern_no_match(self):
        assert _matches_exclude_pattern("foo.py", ["*.md"]) is False
        assert _matches_exclude_pattern("readme.txt", ["*.md"]) is False

    def test_path_pattern_with_slash(self):
        assert _matches_exclude_pattern("memories/session.md", ["memories/*"]) is True
        assert _matches_exclude_pattern("logs/debug.log", ["logs/*"]) is True

    def test_path_pattern_no_match(self):
        assert _matches_exclude_pattern("src/memories/file.md", ["memories/*"]) is False
        assert _matches_exclude_pattern("config.json", ["memories/*"]) is False

    def test_wildcard_matches_everything(self):
        assert _matches_exclude_pattern("any/file.txt", ["*"]) is True
        assert _matches_exclude_pattern("CLAUDE.md", ["*"]) is True

    def test_empty_patterns(self):
        assert _matches_exclude_pattern("anything.txt", []) is False

    def test_multiple_patterns(self):
        patterns = ["*.log", "memories/*", "*.tmp"]
        assert _matches_exclude_pattern("debug.log", patterns) is True
        assert _matches_exclude_pattern("memories/x.md", patterns) is True
        assert _matches_exclude_pattern("cache.tmp", patterns) is True
        assert _matches_exclude_pattern("CLAUDE.md", patterns) is False


# --- Tests for list_all_agent_files ---

class TestListAllAgentFiles:

    def test_lists_files_recursively(self, agent_workspace):
        files = file_service.list_all_agent_files(agent_workspace["name"])
        paths = {f["path"] for f in files}
        assert "CLAUDE.md" in paths
        assert "SOUL.md" in paths
        assert "config.json" in paths
        assert "skills/greeting/SKILL.md" in paths
        assert "memories/session.md" in paths
        assert "logs/debug.log" in paths

    def test_reads_file_content(self, agent_workspace):
        files = file_service.list_all_agent_files(agent_workspace["name"])
        claude_file = next(f for f in files if f["path"] == "CLAUDE.md")
        assert "!{AGENT_NAME}" in claude_file["content"]
        assert "!{PROJECT}" in claude_file["content"]

    def test_skips_git_dir(self, agent_workspace):
        (agent_workspace["workspace"] / ".git").mkdir()
        (agent_workspace["workspace"] / ".git" / "config").write_text("git config")
        files = file_service.list_all_agent_files(agent_workspace["name"])
        paths = {f["path"] for f in files}
        assert ".git/config" not in paths

    def test_nonexistent_workspace_returns_empty(self, agent_workspace):
        files = file_service.list_all_agent_files("workspace-nonexistent")
        assert files == []


# --- Tests for create_blueprint with import ---

class TestCreateBlueprintWithImport:

    @pytest.mark.asyncio
    async def test_create_without_import(self):
        result = await blueprint_service.create_blueprint("test-bp", "desc")
        assert result["name"] == "test-bp"
        assert result["description"] == "desc"
        assert result["imported_file_count"] == 0

    @pytest.mark.asyncio
    async def test_create_with_import(self, agent_workspace):
        agent_id = await version_db.get_or_create_agent(agent_workspace["name"])

        result = await blueprint_service.create_blueprint(
            "import-bp", "imported", source_agent_id=agent_id
        )
        assert result["imported_file_count"] > 0
        assert result["name"] == "import-bp"

        # Verify files were imported as templates
        files = await blueprint_service.list_blueprint_files(result["id"])
        paths = {f["file_path"] for f in files}
        assert "CLAUDE.md" in paths
        assert "SOUL.md" in paths

    @pytest.mark.asyncio
    async def test_create_with_import_and_excludes(self, agent_workspace):
        agent_id = await version_db.get_or_create_agent(agent_workspace["name"])

        result = await blueprint_service.create_blueprint(
            "exclude-bp", "with excludes",
            source_agent_id=agent_id,
            exclude_patterns=["memories/*", "logs/*", "*.json"]
        )
        files = await blueprint_service.list_blueprint_files(result["id"])
        paths = {f["file_path"] for f in files}

        assert "CLAUDE.md" in paths
        assert "SOUL.md" in paths
        assert "skills/greeting/SKILL.md" in paths

        # Excluded files should not be present
        assert "memories/session.md" not in paths
        assert "logs/debug.log" not in paths
        assert "config.json" not in paths

    @pytest.mark.asyncio
    async def test_create_with_exclude_all(self, agent_workspace):
        agent_id = await version_db.get_or_create_agent(agent_workspace["name"])

        result = await blueprint_service.create_blueprint(
            "empty-bp", "all excluded",
            source_agent_id=agent_id,
            exclude_patterns=["*"]
        )
        assert result["imported_file_count"] == 0

    @pytest.mark.asyncio
    async def test_import_nonexistent_agent(self):
        with pytest.raises(FileNotFoundError, match="Source agent not found"):
            await blueprint_service.create_blueprint(
                "bad-bp", "bad source", source_agent_id=99999
            )

    @pytest.mark.asyncio
    async def test_import_from_virtual_agent(self):
        virtual_id = await version_db.get_or_create_virtual_agent("_blueprint-test")
        with pytest.raises(ValueError, match="Cannot import from a blueprint"):
            await blueprint_service.create_blueprint(
                "virtual-bp", "from virtual", source_agent_id=virtual_id
            )

    @pytest.mark.asyncio
    async def test_import_workspace_dir_missing(self, agent_workspace):
        # Agent exists in DB but has no workspace directory
        agent_id = await version_db.get_or_create_agent("workspace-deleted")
        with pytest.raises(FileNotFoundError, match="workspace directory not found"):
            await blueprint_service.create_blueprint(
                "missing-ws-bp", "missing workspace",
                source_agent_id=agent_id
            )

    @pytest.mark.asyncio
    async def test_variables_extracted_from_imported_files(self, agent_workspace):
        agent_id = await version_db.get_or_create_agent(agent_workspace["name"])

        result = await blueprint_service.create_blueprint(
            "vars-bp", "var test", source_agent_id=agent_id
        )
        variables = await blueprint_service.get_blueprint_variables(result["id"])
        var_names = [v["name"] for v in variables]
        assert "AGENT_NAME" in var_names
        assert "PROJECT" in var_names
        assert "GREETING_STYLE" in var_names

    @pytest.mark.asyncio
    async def test_duplicate_name_raises(self):
        await blueprint_service.create_blueprint("dup-bp", "first")
        with pytest.raises(Exception):
            await blueprint_service.create_blueprint("dup-bp", "second")
