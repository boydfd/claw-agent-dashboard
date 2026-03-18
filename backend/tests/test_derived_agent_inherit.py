"""Tests for derived-agent template inheritance, resync, and resync-all."""
import os
import tempfile

import pytest
import pytest_asyncio

# Patch config before importing services
_test_dir = tempfile.mkdtemp(prefix="derive-test-")
os.environ["AGENTS_DIR"] = os.path.join(_test_dir, "agents")
os.environ["DATA_DIR"] = os.path.join(_test_dir, "data")
os.environ["AGENTS_HOST_DIR"] = ""

import backend.app.config as cfg
cfg.AGENTS_DIR = os.path.join(_test_dir, "agents")
cfg.DATA_DIR = os.path.join(_test_dir, "data")
cfg.AGENTS_HOST_DIR = ""

from backend.app.services import (
    version_db, file_service, blueprint_service, template_service,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db(tmp_path):
    """Initialize a fresh DB for each test."""
    db_path = tmp_path / "versions.db"
    version_db.DB_PATH = db_path
    if version_db._db is not None:
        await version_db._db.close()
        version_db._db = None
    await version_db.init_db()

    # Point AGENTS_DIR at tmp_path so derive can mkdir
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(exist_ok=True)
    cfg.AGENTS_DIR = str(agents_dir)
    file_service.AGENTS_DIR = str(agents_dir)

    yield

    if version_db._db is not None:
        await version_db._db.close()
        version_db._db = None


async def _create_blueprint_with_files():
    """Helper: create a blueprint with two template files containing variables."""
    bp = await blueprint_service.create_blueprint("test-bp", "test blueprint")
    await blueprint_service.add_blueprint_file(
        bp["id"], "CLAUDE.md", "# Agent !{AGENT_NAME}\nProject: !{PROJECT}"
    )
    await blueprint_service.add_blueprint_file(
        bp["id"], "skills/greeting/SKILL.md", "Hello !{GREETING_STYLE}"
    )
    return bp


async def _derive_agent(bp_id, name="derived", variables=None):
    """Helper: derive an agent from a blueprint."""
    return await blueprint_service.derive_agent(
        bp_id, name, variables=variables or {"AGENT_NAME": "Sizao", "PROJECT": "demo"}
    )


# ---------------------------------------------------------------------------
# lookup_or_create — derived agents inherit blueprint template
# ---------------------------------------------------------------------------

class TestLookupOrCreateDerived:

    @pytest.mark.asyncio
    async def test_returns_blueprint_template_for_derived_agent(self):
        """Derived agent should inherit blueprint raw template (with !{VAR}),
        not lazy-load rendered content from disk."""
        bp = await _create_blueprint_with_files()
        result = await _derive_agent(bp["id"])
        agent_id = result["agent_id"]

        # lookup_or_create for derived agent should return blueprint template
        template = await template_service.lookup_or_create(agent_id, "CLAUDE.md")
        assert "!{AGENT_NAME}" in template["content"]
        assert "!{PROJECT}" in template["content"]
        # Template should belong to the blueprint's virtual agent, not derived
        bp_data = await version_db.get_blueprint(bp["id"])
        assert template["agent_id"] == bp_data["agent_id"]

    @pytest.mark.asyncio
    async def test_returns_own_template_for_overridden_file(self):
        """If a derived agent has overridden a file (has its own template
        record), lookup_or_create should return that record."""
        bp = await _create_blueprint_with_files()
        result = await _derive_agent(bp["id"])
        agent_id = result["agent_id"]

        # Manually create an override template record
        override_content = "# Custom Agent Sizao - manually edited"
        await version_db.create_template(
            agent_id=agent_id, file_path="CLAUDE.md", content=override_content
        )
        derivation = await version_db.get_derivation_by_agent_id(agent_id)
        await version_db.add_override(derivation["id"], "CLAUDE.md")

        template = await template_service.lookup_or_create(agent_id, "CLAUDE.md")
        assert template["content"] == override_content
        assert template["agent_id"] == agent_id

    @pytest.mark.asyncio
    async def test_lazy_loads_for_non_derived_agent(self):
        """Non-derived agents should still lazy-load from disk as before."""
        agent_name = "workspace-standalone"
        agent_id = await version_db.get_or_create_agent(agent_name)

        # Create a file on disk
        import pathlib
        ws = pathlib.Path(cfg.AGENTS_DIR) / agent_name
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "README.md").write_text("standalone content")

        template = await template_service.lookup_or_create(agent_id, "README.md")
        assert template["content"] == "standalone content"
        assert template["agent_id"] == agent_id


# ---------------------------------------------------------------------------
# render_template_content — 3-layer variable merge for derived agents
# ---------------------------------------------------------------------------

class TestRenderTemplateContentDerived:

    @pytest.mark.asyncio
    async def test_renders_with_derived_agent_variables(self):
        """When requesting_agent_id is a derived agent, render should use
        the 3-layer variable merge (global → blueprint → agent)."""
        bp = await _create_blueprint_with_files()
        result = await _derive_agent(bp["id"], variables={
            "AGENT_NAME": "Sizao",
            "PROJECT": "my-project",
        })
        agent_id = result["agent_id"]

        # Get the blueprint template
        bp_data = await version_db.get_blueprint(bp["id"])
        template = await version_db.get_template_by_path(bp_data["agent_id"], "CLAUDE.md")

        rendered = await template_service.render_template_content(
            template["id"], requesting_agent_id=agent_id
        )
        assert "Sizao" in rendered["content"]
        assert "my-project" in rendered["content"]
        assert "!{" not in rendered["content"]

    @pytest.mark.asyncio
    async def test_renders_with_owner_variables_when_no_requesting_agent(self):
        """Without requesting_agent_id, should use the template owner's
        (blueprint's) variables — which may leave vars unresolved."""
        bp = await _create_blueprint_with_files()
        bp_data = await version_db.get_blueprint(bp["id"])
        template = await version_db.get_template_by_path(bp_data["agent_id"], "CLAUDE.md")

        rendered = await template_service.render_template_content(template["id"])
        # No agent-scoped variables set for the blueprint's virtual agent,
        # so variables remain unresolved
        assert "!{AGENT_NAME}" in rendered["content"]

    @pytest.mark.asyncio
    async def test_same_template_unresolved_without_agent_resolved_with(self):
        """Reproduces the UI bug: same template ID shows unresolved
        variables when agent_id is omitted, but resolves correctly when
        the derived agent's ID is passed."""
        bp = await _create_blueprint_with_files()
        result = await _derive_agent(bp["id"], variables={
            "AGENT_NAME": "Sizao",
            "PROJECT": "demo",
        })
        agent_id = result["agent_id"]

        bp_data = await version_db.get_blueprint(bp["id"])
        template = await version_db.get_template_by_path(bp_data["agent_id"], "CLAUDE.md")
        tid = template["id"]

        # Without agent_id — unresolved (the bug)
        without = await template_service.render_template_content(tid)
        assert "!{AGENT_NAME}" in without["content"]
        assert len(without["warnings"]) > 0

        # With agent_id — resolved (the fix)
        with_agent = await template_service.render_template_content(
            tid, requesting_agent_id=agent_id
        )
        assert "Sizao" in with_agent["content"]
        assert "!{" not in with_agent["content"]
        assert len(with_agent["warnings"]) == 0


# ---------------------------------------------------------------------------
# resync_all_files — bulk restore
# ---------------------------------------------------------------------------

class TestResyncAllFiles:

    @pytest.mark.asyncio
    async def test_clears_overrides_and_resyncs(self):
        """resync_all_files should remove all overrides and re-render
        every file from the blueprint."""
        bp = await _create_blueprint_with_files()
        result = await _derive_agent(bp["id"])
        agent_id = result["agent_id"]

        # Mark some files as overridden
        derivation = await version_db.get_derivation_by_agent_id(agent_id)
        await version_db.add_override(derivation["id"], "CLAUDE.md")
        await version_db.add_override(derivation["id"], "skills/greeting/SKILL.md")

        # Verify overrides exist
        overrides = await version_db.list_overrides(derivation["id"])
        assert len(overrides) == 2

        # Resync all
        resync_result = await blueprint_service.resync_all_files(agent_id)
        assert resync_result["resynced"] is True

        # All overrides should be gone
        overrides = await version_db.list_overrides(derivation["id"])
        assert len(overrides) == 0

    @pytest.mark.asyncio
    async def test_deletes_stale_derived_templates(self):
        """resync_all_files should delete template records that were
        erroneously created for the derived agent (compat fix)."""
        bp = await _create_blueprint_with_files()
        result = await _derive_agent(bp["id"])
        agent_id = result["agent_id"]

        # Simulate the old lookup_or_create bug: create template records
        # owned by the derived agent with rendered (no !{VAR}) content
        await version_db.create_template(
            agent_id=agent_id, file_path="CLAUDE.md",
            content="# Agent Sizao\nProject: demo"
        )
        await version_db.create_template(
            agent_id=agent_id, file_path="skills/greeting/SKILL.md",
            content="Hello formal"
        )

        # Verify stale templates exist
        stale = await version_db.list_templates(agent_id=agent_id)
        assert len(stale) == 2

        # Resync all
        resync_result = await blueprint_service.resync_all_files(agent_id)
        assert resync_result["deleted_stale_templates"] == 2

        # Stale templates should be gone
        remaining = await version_db.list_templates(agent_id=agent_id)
        assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_rerenders_files_on_disk(self):
        """After resync_all, disk files should contain the freshly
        rendered content from the blueprint templates."""
        bp = await _create_blueprint_with_files()
        result = await _derive_agent(bp["id"], variables={
            "AGENT_NAME": "Restored",
            "PROJECT": "proj",
        })
        agent_id = result["agent_id"]
        ws_name = result["workspace_name"]

        # Tamper with disk file (simulate user edit)
        file_service.write_file(ws_name, "CLAUDE.md", "TAMPERED CONTENT")

        # Resync all
        await blueprint_service.resync_all_files(agent_id)

        # Disk file should have rendered blueprint content
        file_data = file_service.read_file(ws_name, "CLAUDE.md")
        assert "Restored" in file_data["content"]
        assert "proj" in file_data["content"]
        assert "TAMPERED" not in file_data["content"]

    @pytest.mark.asyncio
    async def test_resync_all_non_derived_raises(self):
        """resync_all_files should raise for non-derived agents."""
        agent_id = await version_db.get_or_create_agent("workspace-standalone")
        with pytest.raises(ValueError, match="not derived"):
            await blueprint_service.resync_all_files(agent_id)


# ---------------------------------------------------------------------------
# clear_all_overrides
# ---------------------------------------------------------------------------

class TestClearAllOverrides:

    @pytest.mark.asyncio
    async def test_clears_all(self):
        bp = await _create_blueprint_with_files()
        result = await _derive_agent(bp["id"])
        derivation = await version_db.get_derivation_by_agent_id(result["agent_id"])

        await version_db.add_override(derivation["id"], "CLAUDE.md")
        await version_db.add_override(derivation["id"], "skills/greeting/SKILL.md")

        count = await version_db.clear_all_overrides(derivation["id"])
        assert count == 2

        overrides = await version_db.list_overrides(derivation["id"])
        assert len(overrides) == 0

    @pytest.mark.asyncio
    async def test_clears_none(self):
        bp = await _create_blueprint_with_files()
        result = await _derive_agent(bp["id"])
        derivation = await version_db.get_derivation_by_agent_id(result["agent_id"])

        count = await version_db.clear_all_overrides(derivation["id"])
        assert count == 0
