"""Read-only security audit — aggregates agents, skills, variables, and env hints."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# Heuristic patterns in workspace markdown (TOOLS.md, AGENTS.md, skills/*/SKILL.md).
# Severity is informational — review context manually.
_CONTENT_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\bcurl\b", re.I), "CURL", "info"),
    (re.compile(r"\bwget\b", re.I), "WGET", "info"),
    (re.compile(r"\brm\s+-rf\b"), "RM_RF", "warning"),
    (re.compile(r"\bchmod\s+777\b"), "CHMOD_777", "info"),
    (re.compile(r"\bsudo\b"), "SUDO", "info"),
    (re.compile(r"eval\s*\("), "EVAL_CALL", "warning"),
    (re.compile(r"subprocess\.(?:call|run|Popen)", re.I), "PYTHON_SUBPROCESS", "info"),
    (re.compile(r"child_process|execSync|spawn\s*\(", re.I), "NODE_CHILD_PROCESS", "info"),
    (re.compile(r"\bpip3?\s+install\b", re.I), "PIP_INSTALL", "info"),
    (re.compile(r"\bnpm\s+(?:install|i)\b", re.I), "NPM_INSTALL", "info"),
)

_MAX_SCAN_BYTES = 512_000
_MAX_SCAN_LINES = 8_000
_MAX_HITS_PER_FILE = 14
_MAX_TOTAL_SIGNALS = 400
_MAX_VT_FILES = 80
_MAX_OSV_DIRECT_DEPS = 60
_MAX_OSV_QUERY_PACKAGES = 180
_MAX_OPENCLAW_RAW_PREVIEW_BYTES = 200_000
_HTTP_TIMEOUT_SECONDS = 8.0
_SECRET_KEYWORDS = ("secret", "token", "password", "api_key", "apikey", "key")
_SECRET_REF_KEYS = ("secretRef", "keyRef", "tokenRef", "passwordRef", "valueFrom")
_MAX_SESSION_FILES = 24
_MAX_SESSION_LINES_PER_FILE = 800
_MAX_SESSION_RISK_HITS = 120
_SESSION_RISK_CONTEXT_RADIUS = 120

_SESSION_RISK_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\b(sudo|su\s+-|doas)\b", re.I), "SESSION_PRIVILEGE_ESCALATION", "warning"),
    (re.compile(r"\b(chmod\s+777|chown\s+root|setcap\s+)\b", re.I), "SESSION_PRIVILEGE_ESCALATION", "warning"),
    (re.compile(r"\b(curl|wget).+\|\s*(sh|bash|zsh)\b", re.I), "SESSION_REMOTE_EXEC_PIPE", "warning"),
    (re.compile(r"\bnpm\s+(?:install|i)\s+(-g|--global)\b", re.I), "SESSION_INSTALL_GLOBAL_PACKAGE", "warning"),
    (re.compile(r"\b(pnpm|yarn|npm)\s+(?:add|install|i)\b", re.I), "SESSION_INSTALL_PACKAGE", "info"),
    (re.compile(r"\b(?:openclaw\s+skill\s+install|skill\s+install)\b", re.I), "SESSION_INSTALL_SKILL", "warning"),
    (re.compile(r"\b(?:openclaw\s+plugin\s+install|plugin\s+install)\b", re.I), "SESSION_INSTALL_PLUGIN", "warning"),
    (re.compile(r"\bclawhub\s+install\b", re.I), "SESSION_INSTALL_SKILL", "warning"),
    (re.compile(r"\bclawhub\s+install\s+github\b", re.I), "SESSION_EXTERNAL_INTEGRATION_INSTALL", "warning"),
    (re.compile(r"\b(set\s+up|install|enable)\b.{0,48}\b(plugin|composio|openclaw-plugin)\b", re.I), "SESSION_PLUGIN_SETUP_REQUEST", "warning"),
    (re.compile(r"\b(ignore|bypass|disable)\b.{0,48}\b(warning|mismatch|verification|signature)\b", re.I), "SESSION_WARNING_BYPASS_REQUEST", "warning"),
    (re.compile(r"\bhttps?://[^\s]*registry\.npmjs\.org/[^\s]+", re.I), "SESSION_EXTERNAL_PACKAGE_INSTRUCTION", "info"),
    # OWASP LLM01 - Prompt Injection / Jailbreak patterns
    (re.compile(r"\b(jailbreak|jail-broken|override|disregard|bypass|ignore)\b.{0,80}\b(system\s+prompt|developer\s+message|instructions?|policy|safety|rules?|restrictions?)\b", re.I), "SESSION_PROMPT_INJECTION_ATTEMPT", "warning"),
    (re.compile(r"\b(reveal|show|print|leak|expose)\b.{0,80}\b(system\s+prompt|developer\s+message)\b", re.I), "SESSION_SYSTEM_PROMPT_LEAKAGE_REQUEST", "warning"),
    (re.compile(r"\b(ignore|bypass|disable)\b.{0,80}\b(instruction|policy|safety|rules?)\b", re.I), "SESSION_PROMPT_INJECTION_ATTEMPT", "warning"),
    # OWASP LLM02 - Sensitive Information Disclosure / Credential exfiltration
    (re.compile(r"\b(begin\s+rsa\s+private\s+key|begin\s+openssh\s+private\s+key|private\s+key)\b", re.I), "SESSION_SENSITIVE_KEY_MATERIAL", "warning"),
    (re.compile(r"\b(authorization|bearer)\b\s*[:=]\s*['\"]?[A-Za-z0-9\-_\.]{8,}", re.I), "SESSION_SENSITIVE_AUTH_HEADER", "warning"),
    (re.compile(r"\b(exfiltrat|exfiltrate|exfil)\b.{0,80}\b(http|https|upload|send)\b", re.I), "SESSION_DATA_EXFILTRATION_ATTEMPT", "warning"),
    # OWASP LLM06 - Excessive Agency / Sensitive file read
    (re.compile(r"\b(~\/\.ssh|\.ssh\/|~\/\.aws|\.aws\/|\/etc\/(passwd|shadow)|\/root\/|\/home\/[^/ ]+\/\.ssh)\b", re.I), "SESSION_SENSITIVE_FILE_READ_REQUEST", "warning"),
    (re.compile(r"\b(read|cat|open|dump)\b.{0,40}\b(~\/\.ssh|\.ssh\/|\.aws\/|\/etc\/(passwd|shadow)|/root/)\b", re.I), "SESSION_SENSITIVE_FILE_READ_REQUEST", "warning"),
    (re.compile(r"\bck__[A-Za-z0-9_-]{10,}\b"), "SESSION_SECRET_EXPOSURE", "warning"),
    (re.compile(r"\b(sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{20,})\b"), "SESSION_SECRET_EXPOSURE", "warning"),
    (re.compile(r"\b(api[_-]?key|appsecret|token|password|secret)\b.{0,24}[:=]\s*['\"]?[A-Za-z0-9_\-./+=]{8,}", re.I), "SESSION_SECRET_EXPOSURE", "warning"),
)

# Lightweight embedded "risk model" (feature scoring, no external LLM dependency).
# This generalizes beyond single-keyword exact matches.
_SESSION_MODEL_FEATURES: dict[str, tuple[re.Pattern[str], int]] = {
    "install_action": (re.compile(r"\b(install|setup|set up|enable|add)\b", re.I), 2),
    "plugin_skill_target": (re.compile(r"\b(plugin|skill|clawhub|composio|npm|pnpm|yarn)\b", re.I), 2),
    "external_pkg_source": (re.compile(r"\b(registry\.npmjs\.org|github\.com|gitlab\.com)\b", re.I), 2),
    "privilege_cmd": (re.compile(r"\b(sudo|su\s+-|doas|setcap|chown\s+root|chmod\s+777)\b", re.I), 4),
    "remote_exec_pipe": (re.compile(r"\b(curl|wget).+\|\s*(sh|bash|zsh)\b", re.I), 5),
    "warning_bypass": (re.compile(r"\b(ignore|bypass|disable|skip)\b.{0,48}\b(warning|verify|verification|mismatch|signature)\b", re.I), 4),
    "secret_literal": (re.compile(r"\b(sk-[A-Za-z0-9_-]{16,}|ck__[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{20,})\b"), 5),
    "secret_assignment": (re.compile(r"\b(api[_-]?key|appsecret|token|password|secret)\b.{0,24}[:=]\s*['\"]?[A-Za-z0-9_\-./+=]{8,}", re.I), 4),
    "sensitive_share": (re.compile(r"\b(my|here is|is:|provide|consumer)\b.{0,24}\b(api key|token|secret|password)\b", re.I), 2),
}

from ..config import (
    AGENTS_DIR,
    DATA_DIR,
    GATEWAY_TOKEN,
    GATEWAY_URL,
    GLOBAL_SKILLS_DIR,
    OPENCLAW_CONFIG_PATH,
    SESSION_DATA_DIR,
    SHARED_SKILLS_DIR,
    resolve_agent_dir,
)
from . import file_service, global_skills as gs, scanner, status as status_service, variable_service, version_db


def _cors_allow_all() -> tuple[bool, int | None]:
    raw = os.environ.get("ALLOWED_ORIGINS", "*").strip()
    if raw == "*":
        return True, None
    parts = [o.strip() for o in raw.split(",") if o.strip()]
    return False, len(parts)


def _load_openclaw_json(config_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Parse openclaw.json (JSONC comments stripped). Returns (data, error_message)."""
    if not config_path.exists():
        return None, None
    try:
        raw = config_path.read_text(encoding="utf-8", errors="replace")
        clean = _strip_jsonc_comments(raw)
        return json.loads(clean), None
    except Exception as e:
        return None, str(e)[:200]


def _credential_configured(value: Any) -> bool:
    """True if token/password appears set (string non-empty or SecretRef dict)."""
    if value is None:
        return False
    if isinstance(value, dict):
        return True
    return bool(str(value).strip())


def _openclaw_security_recommendations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive security-focused checks from parsed openclaw.json (no secret values)."""
    recs: dict[str, dict[str, Any]] = {}

    gw = data.get("gateway")
    if not isinstance(gw, dict):
        recs["OPENCLAW_GATEWAY_BLOCK_MISSING"] = {
            "id": "OPENCLAW_GATEWAY_BLOCK_MISSING",
            "severity": "info",
        }
        return sorted(recs.values(), key=lambda x: (0 if x["severity"] == "warning" else 1, x["id"]))

    bind = gw.get("bind")
    if isinstance(bind, str):
        bind_norm = bind.strip().lower()
    else:
        bind_norm = None

    auth = gw.get("auth")
    if "auth" not in gw:
        recs["GATEWAY_AUTH_BLOCK_MISSING"] = {
            "id": "GATEWAY_AUTH_BLOCK_MISSING",
            "severity": "warning",
        }
        auth = {}
    elif not isinstance(auth, dict):
        auth = {}
    else:
        if len(auth) == 0:
            recs["GATEWAY_AUTH_EMPTY"] = {
                "id": "GATEWAY_AUTH_EMPTY",
                "severity": "warning",
            }

    mode = auth.get("mode") if isinstance(auth, dict) else None
    if isinstance(mode, str):
        mode_norm = mode.strip().lower()
    else:
        mode_norm = None

    token_ok = _credential_configured(auth.get("token")) if isinstance(auth, dict) else False
    password_ok = _credential_configured(auth.get("password")) if isinstance(auth, dict) else False

    if mode_norm == "none":
        recs["GATEWAY_AUTH_MODE_NONE"] = {
            "id": "GATEWAY_AUTH_MODE_NONE",
            "severity": "warning",
        }
        if bind_norm in ("lan", "custom", "tailnet", "auto"):
            recs["GATEWAY_AUTH_NONE_NON_LOOPBACK"] = {
                "id": "GATEWAY_AUTH_NONE_NON_LOOPBACK",
                "severity": "warning",
            }

    if bind_norm == "lan":
        recs["GATEWAY_BIND_LAN"] = {
            "id": "GATEWAY_BIND_LAN",
            "severity": "info",
        }

    if token_ok and password_ok and mode_norm is None:
        recs["GATEWAY_AUTH_MODE_AMBIGUOUS"] = {
            "id": "GATEWAY_AUTH_MODE_AMBIGUOUS",
            "severity": "warning",
        }

    if mode_norm == "token" and not token_ok:
        recs["GATEWAY_TOKEN_UNSET"] = {
            "id": "GATEWAY_TOKEN_UNSET",
            "severity": "warning",
        }

    if mode_norm == "password" and not password_ok:
        recs["GATEWAY_PASSWORD_UNSET"] = {
            "id": "GATEWAY_PASSWORD_UNSET",
            "severity": "warning",
        }

    if mode_norm is None and not token_ok and not password_ok and isinstance(auth, dict) and len(auth) > 0:
        # auth block present with keys but no resolved mode/credentials
        recs["GATEWAY_AUTH_UNCONFIGURED"] = {
            "id": "GATEWAY_AUTH_UNCONFIGURED",
            "severity": "info",
        }

    if mode_norm == "trusted-proxy":
        recs["GATEWAY_TRUSTED_PROXY_MODE"] = {
            "id": "GATEWAY_TRUSTED_PROXY_MODE",
            "severity": "info",
        }

    if data.get("debug") is True:
        recs["OPENCLAW_DEBUG_ENABLED"] = {
            "id": "OPENCLAW_DEBUG_ENABLED",
            "severity": "warning",
        }

    # OWASP LLM06 - Excessive Agency / Unbounded tool/plugin capabilities
    plugins = data.get("plugins")
    if isinstance(plugins, dict):
        allow = plugins.get("allow")
        is_empty_allow = False
        is_wildcard_allow = False
        if allow is None:
            pass
        elif isinstance(allow, list) and len(allow) == 0:
            is_empty_allow = True
        elif isinstance(allow, dict) and len(allow) == 0:
            is_empty_allow = True
        elif isinstance(allow, str) and not allow.strip():
            is_empty_allow = True
        elif allow == "*" or (isinstance(allow, str) and allow.strip() == "*"):
            is_wildcard_allow = True
        if is_empty_allow:
            recs["OPENCLAW_PLUGINS_ALLOW_EMPTY"] = {
                "id": "OPENCLAW_PLUGINS_ALLOW_EMPTY",
                "severity": "warning",
            }
        if is_wildcard_allow:
            recs["OPENCLAW_PLUGINS_ALLOW_WILDCARD"] = {
                "id": "OPENCLAW_PLUGINS_ALLOW_WILDCARD",
                "severity": "warning",
            }

    return sorted(recs.values(), key=lambda x: (0 if x["severity"] == "warning" else 1, x["id"]))


def _is_secret_like_key(key: str) -> bool:
    k = key.strip().lower()
    return any(part in k for part in _SECRET_KEYWORDS)


def _count_openclaw_secrets(data: Any) -> dict[str, Any]:
    """Recursively count secret-like values/references in openclaw config (no plaintext output)."""
    refs: list[str] = []
    inline: list[str] = []

    def walk(node: Any, path: str):
        if isinstance(node, dict):
            lower_keys = {str(k).lower() for k in node.keys()}
            # SecretRef-like object
            if any(r.lower() in lower_keys for r in _SECRET_REF_KEYS):
                refs.append(path or "$")
            for k, v in node.items():
                key = str(k)
                child_path = f"{path}.{key}" if path else key
                if _is_secret_like_key(key):
                    # plain inline secret-ish string
                    if isinstance(v, str) and v.strip():
                        inline.append(child_path)
                    # reference object under secret-ish field (still secret managed)
                    elif isinstance(v, dict) and any(r.lower() in {str(x).lower() for x in v.keys()} for r in _SECRET_REF_KEYS):
                        refs.append(child_path)
                walk(v, child_path)
        elif isinstance(node, list):
            for idx, it in enumerate(node):
                walk(it, f"{path}[{idx}]")

    walk(data, "")
    # dedupe while preserving order
    def uniq(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in items:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    refs_u = uniq(refs)
    inline_u = uniq(inline)
    return {
        "secret_ref_count": len(refs_u),
        "inline_secret_like_count": len(inline_u),
        "secret_ref_paths": refs_u[:60],
        "inline_secret_like_paths": inline_u[:60],
    }


def _strip_jsonc_comments(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        idx = 0
        while True:
            comment_idx = line.find("//", idx)
            if comment_idx < 0:
                break
            if comment_idx > 0 and line[comment_idx - 1] == ":":
                idx = comment_idx + 2
                continue
            if '"' not in line[comment_idx:]:
                line = line[:comment_idx]
            break
        lines.append(line)
    return "\n".join(lines)


def _openclaw_preview(config_path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {
        "path": str(config_path),
        "exists": config_path.exists(),
        "parsed": False,
        "top_level_keys": [],
        "agents_in_registry_count": 0,
        "agents_registry_declared": False,
        "bindings_count": 0,
        "parse_error": None,
        "gateway_bind": None,
        "gateway_auth_mode": None,
        "gateway_auth_token_configured": None,
        "gateway_auth_password_configured": None,
        "secrets": {
            "secret_ref_count": 0,
            "inline_secret_like_count": 0,
            "secret_ref_paths": [],
            "inline_secret_like_paths": [],
        },
        "security_recommendations": [],
        "raw_text": None,
        "raw_text_truncated": False,
    }
    if not out["exists"]:
        return out
    try:
        raw = config_path.read_text(encoding="utf-8", errors="replace")
        if len(raw.encode("utf-8", errors="replace")) > _MAX_OPENCLAW_RAW_PREVIEW_BYTES:
            encoded = raw.encode("utf-8", errors="replace")
            clipped = encoded[:_MAX_OPENCLAW_RAW_PREVIEW_BYTES]
            out["raw_text"] = clipped.decode("utf-8", errors="ignore")
            out["raw_text_truncated"] = True
        else:
            out["raw_text"] = raw
    except Exception:
        out["raw_text"] = None

    data, parse_err = _load_openclaw_json(config_path)
    if data is None:
        out["parse_error"] = parse_err or "Failed to read or parse openclaw.json"
        return out
    try:
        out["parsed"] = True
        out["top_level_keys"] = sorted(data.keys())[:50]
        agents_obj = data.get("agents")
        if isinstance(agents_obj, dict) and "list" in agents_obj:
            out["agents_registry_declared"] = True
        agents_list = agents_obj.get("list", []) if isinstance(agents_obj, dict) else []
        if isinstance(agents_list, list):
            out["agents_in_registry_count"] = len(agents_list)
        bindings = data.get("bindings", [])
        if isinstance(bindings, list):
            out["bindings_count"] = len(bindings)

        gw = data.get("gateway")
        if isinstance(gw, dict):
            out["gateway_bind"] = gw.get("bind")
            auth = gw.get("auth")
            if isinstance(auth, dict):
                out["gateway_auth_mode"] = auth.get("mode")
                out["gateway_auth_token_configured"] = _credential_configured(auth.get("token"))
                out["gateway_auth_password_configured"] = _credential_configured(auth.get("password"))
        out["secrets"] = _count_openclaw_secrets(data)
        out["security_recommendations"] = _openclaw_security_recommendations(data)
        if (out["secrets"].get("inline_secret_like_count") or 0) > 0:
            out["security_recommendations"].append({
                "id": "OPENCLAW_INLINE_SECRETS_DETECTED",
                "severity": "warning",
            })
        if (out["secrets"].get("secret_ref_count") or 0) > 0:
            out["security_recommendations"].append({
                "id": "OPENCLAW_SECRET_REFS_PRESENT",
                "severity": "info",
            })
        out["security_recommendations"] = sorted(
            out["security_recommendations"],
            key=lambda x: (0 if x["severity"] == "warning" else 1, x["id"]),
        )
    except Exception as e:
        out["parse_error"] = str(e)[:200]
    return out


def _count_files_in_skill_tree(items: list[dict]) -> int:
    n = 0
    for it in items:
        if it.get("type") == "file":
            n += 1
        elif it.get("type") == "directory" and it.get("children"):
            n += _count_files_in_skill_tree(it["children"])
    return n


async def _agent_skill_rows(agent_name: str) -> list[dict[str, Any]]:
    skills = await file_service.list_agent_skills_async(agent_name)
    rows = []
    for s in skills:
        name = s["name"]
        tree = await file_service.list_skill_files_async(agent_name, name)
        rows.append({
            "name": name,
            "display_name": s.get("display_name", name),
            "file_count": _count_files_in_skill_tree(tree),
        })
    return rows


async def _global_source_rows() -> list[dict[str, Any]]:
    sources_out = []
    for src in gs.list_sources():
        source = src["source"]
        skills = gs.list_skills(source)
        skill_rows = []
        for sk in skills:
            tree = gs.list_skill_files(source, sk["name"])
            skill_rows.append({
                "name": sk["name"],
                "display_name": sk.get("display_name", sk["name"]),
                "file_count": _count_files_in_skill_tree(tree),
            })
        sources_out.append({
            "source": source,
            "label": src.get("name", source),
            "path": src.get("path", ""),
            "skill_count": len(skill_rows),
            "skills": skill_rows,
        })
    return sources_out


def _policy_files(agent_name: str) -> dict[str, bool]:
    base = Path(AGENTS_DIR) / resolve_agent_dir(agent_name)
    names = ("TOOLS.md", "AGENTS.md", "BOOTSTRAP.md")
    return {n: (base / n).is_file() for n in names}


def _scan_text_file(path: Path) -> list[dict[str, Any]]:
    """Return rule hits for one file (line-level, capped)."""
    hits: list[dict[str, Any]] = []
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hits
    if len(raw) > _MAX_SCAN_BYTES:
        raw = raw[:_MAX_SCAN_BYTES]
    seen: set[tuple[int, str]] = set()
    for line_num, line in enumerate(raw.splitlines(), start=1):
        if line_num > _MAX_SCAN_LINES:
            break
        if len(hits) >= _MAX_HITS_PER_FILE:
            break
        for pattern, rule_id, severity in _CONTENT_RULES:
            if pattern.search(line):
                key = (line_num, rule_id)
                if key in seen:
                    continue
                seen.add(key)
                hits.append({
                    "rule": rule_id,
                    "severity": severity,
                    "line": line_num,
                    "preview": line.strip()[:240],
                })
                if len(hits) >= _MAX_HITS_PER_FILE:
                    break
    return hits


def _session_jsonl_candidates(agent_name: str) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    resolved = resolve_agent_dir(agent_name)
    agent_short = resolved.replace("workspace-", "")
    bases = [
        # Workspace-style session paths
        Path(AGENTS_DIR) / resolved / "sessions",
        Path(AGENTS_DIR) / f"workspace-{agent_short}" / "sessions",
        # Agent registry-style paths (used by status service)
        Path(AGENTS_DIR) / "agents" / agent_short / "sessions",
        Path(AGENTS_DIR) / "agents" / resolved / "sessions",
        # Host mounted session data paths
        Path(SESSION_DATA_DIR) / agent_short / "sessions",
        Path(SESSION_DATA_DIR) / "agents" / agent_short / "sessions",
    ]
    for base in bases:
        if not base.is_dir():
            continue
        for fp in sorted(base.glob("*.jsonl"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
            if fp.name.endswith(".deleted.jsonl") or fp.name.endswith(".lock"):
                continue
            key = str(fp.resolve())
            if key in seen:
                continue
            seen.add(key)
            out.append(fp)
            if len(out) >= _MAX_SESSION_FILES:
                return out
    return out


def _stringify_session_message_line(line_obj: dict[str, Any]) -> tuple[str, str, str]:
    msg = line_obj.get("message") or line_obj
    role = str(msg.get("role") or line_obj.get("role") or "unknown")
    ts = str(line_obj.get("timestamp") or msg.get("timestamp") or "")
    content = msg.get("content", "")
    if isinstance(content, str):
        return role, ts, content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                bt = str(block.get("type") or "text")
                if bt == "text":
                    parts.append(str(block.get("text") or ""))
                elif bt == "toolCall":
                    args = block.get("arguments")
                    args_text = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
                    parts.append(f"[toolCall {block.get('name', 'unknown')}] {args_text}")
                elif bt == "toolResult":
                    t = block.get("text", block.get("content", ""))
                    parts.append(str(t if isinstance(t, str) else json.dumps(t, ensure_ascii=False)))
                elif bt == "thinking":
                    parts.append(str(block.get("thinking") or ""))
                else:
                    parts.append(str(block.get("text") or json.dumps(block, ensure_ascii=False)))
        return role, ts, "\n".join([p for p in parts if p]).strip()
    return role, ts, str(content)


def _infer_session_risk_with_embedded_model(text: str) -> list[dict[str, Any]]:
    """Infer risk intents using weighted feature co-occurrence (mini embedded model)."""
    if not text:
        return []
    scores: dict[str, int] = {
        "SESSION_SECRET_EXPOSURE": 0,
        "SESSION_SUPPLY_CHAIN_INSTALL": 0,
        "SESSION_PRIVILEGE_ESCALATION": 0,
        "SESSION_REMOTE_EXEC_PIPE": 0,
        "SESSION_WARNING_BYPASS_REQUEST": 0,
    }
    signals: dict[str, list[str]] = {k: [] for k in scores.keys()}

    def add(code: str, n: int, sig: str):
        scores[code] += n
        if sig not in signals[code]:
            signals[code].append(sig)

    for feat, (pattern, weight) in _SESSION_MODEL_FEATURES.items():
        m = pattern.search(text)
        if not m:
            continue
        token = m.group(0)[:80]
        if feat in {"secret_literal", "secret_assignment", "sensitive_share"}:
            add("SESSION_SECRET_EXPOSURE", weight, token)
        if feat in {"install_action", "plugin_skill_target", "external_pkg_source"}:
            add("SESSION_SUPPLY_CHAIN_INSTALL", weight, token)
        if feat == "privilege_cmd":
            add("SESSION_PRIVILEGE_ESCALATION", weight, token)
        if feat == "remote_exec_pipe":
            add("SESSION_REMOTE_EXEC_PIPE", weight, token)
        if feat == "warning_bypass":
            add("SESSION_WARNING_BYPASS_REQUEST", weight, token)

    out: list[dict[str, Any]] = []
    for code, score in scores.items():
        if score <= 0:
            continue
        sev = "warning" if score >= 5 else "info"
        out.append({
            "rule": code,
            "severity": sev,
            "score": score,
            "signals": signals.get(code, [])[:5],
            "matched_text": (signals.get(code, [""])[0] or "")[:180],
        })
    # Keep strongest intents first.
    out.sort(key=lambda x: (0 if x["severity"] == "warning" else 1, -x["score"], x["rule"]))
    return out


def _detect_session_risk(text: str) -> dict[str, Any] | None:
    """Blend precise regex rules + embedded feature model."""
    candidates: list[dict[str, Any]] = []
    for pattern, rule_id, severity in _SESSION_RISK_RULES:
        m = pattern.search(text or "")
        if not m:
            continue
        candidates.append({
            "rule": rule_id,
            "severity": severity,
            "score": 10 if severity == "warning" else 6,
            "matched_text": m.group(0)[:180],
            "signals": [m.group(0)[:80]],
        })
    candidates.extend(_infer_session_risk_with_embedded_model(text or ""))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (0 if x["severity"] == "warning" else 1, -int(x.get("score", 0)), x["rule"]))
    return candidates[0]


def _scan_session_risks(agent_names: list[str]) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    scanned_files = 0
    for agent_name in agent_names:
        # Align with Agents page session source:
        # 1) read sessions via status service
        # 2) read transcript via status session messages API path
        resolved_agent = resolve_agent_dir(agent_name)
        if agent_name == "workspace-main" or resolved_agent == "workspace":
            agent_short = "main"
        elif resolved_agent.startswith("workspace-"):
            agent_short = resolved_agent.replace("workspace-", "", 1)
        else:
            agent_short = resolved_agent
        status_agent_candidates = [
            resolved_agent,
            f"agents/{agent_short}",
            agent_short,
            agent_name,
        ]
        session_rows: list[dict[str, Any]] = []
        chosen_status_agent = None
        for cand in status_agent_candidates:
            try:
                st = status_service.get_agent_status(cand)
                rows = st.get("sessions") or []
                if rows:
                    session_rows = rows
                    chosen_status_agent = cand
                    break
            except Exception:
                continue

        scanned_with_status = False
        for sess in session_rows:
            sid = str(sess.get("session_id") or "").strip()
            if not sid:
                continue
            scanned_files += 1
            scanned_with_status = True
            try:
                msg_page = status_service.get_session_messages(chosen_status_agent or resolved_agent, sid, offset=0, limit=200)
                msgs = msg_page.get("messages") or []
            except Exception:
                msgs = []
            for msg in msgs:
                if len(hits) >= _MAX_SESSION_RISK_HITS:
                    break
                # status service returns parsed content blocks
                parts: list[str] = []
                for b in (msg.get("content") or []):
                    bt = str((b or {}).get("type") or "")
                    if bt == "text":
                        parts.append(str((b or {}).get("text") or ""))
                    elif bt == "toolCall":
                        parts.append(f"[toolCall {(b or {}).get('name', 'unknown')}] {str((b or {}).get('arguments') or '')}")
                    elif bt == "toolResult":
                        parts.append(str((b or {}).get("text") or ""))
                    elif bt == "thinking":
                        parts.append(str((b or {}).get("text") or ""))
                text = "\n".join([p for p in parts if p]).strip()
                if not text:
                    continue
                role = str(msg.get("role") or "unknown")
                ts = str(msg.get("timestamp") or "")
                detected = _detect_session_risk(text)
                if not detected:
                    continue
                needle = detected.get("matched_text") or ""
                idx = text.lower().find(str(needle).lower()) if needle else -1
                if idx < 0:
                    idx = 0
                st = max(0, idx - _SESSION_RISK_CONTEXT_RADIUS)
                ed = min(len(text), idx + max(len(str(needle)), 1) + _SESSION_RISK_CONTEXT_RADIUS)
                snippet = text[st:ed].strip().replace("\r\n", "\n")
                hits.append({
                    "severity": detected["severity"],
                    "rule": detected["rule"],
                    "risk_score": detected.get("score", 0),
                    "model_signals": detected.get("signals", []),
                    "agent_name": agent_name,
                    "session_file": f"{sid}.jsonl",
                    "timestamp": ts or None,
                    "role": role,
                    "matched_text": str(needle)[:180],
                    "context": snippet[:900],
                })

        # Fallback: direct jsonl scan if status pipeline finds nothing
        if scanned_with_status:
            continue
        for fp in _session_jsonl_candidates(agent_name):
            if len(hits) >= _MAX_SESSION_RISK_HITS:
                break
            scanned_files += 1
            try:
                with fp.open("r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except OSError:
                continue
            if len(lines) > _MAX_SESSION_LINES_PER_FILE:
                lines = lines[-_MAX_SESSION_LINES_PER_FILE:]
            for raw in lines:
                if len(hits) >= _MAX_SESSION_RISK_HITS:
                    break
                s = raw.strip()
                if not s:
                    continue
                try:
                    entry = json.loads(s)
                except Exception:
                    continue
                role, ts, text = _stringify_session_message_line(entry)
                if not text:
                    continue
                detected = _detect_session_risk(text)
                if not detected:
                    continue
                needle = detected.get("matched_text") or ""
                idx = text.lower().find(str(needle).lower()) if needle else -1
                if idx < 0:
                    idx = 0
                st = max(0, idx - _SESSION_RISK_CONTEXT_RADIUS)
                ed = min(len(text), idx + max(len(str(needle)), 1) + _SESSION_RISK_CONTEXT_RADIUS)
                snippet = text[st:ed].strip().replace("\r\n", "\n")
                hits.append({
                    "severity": detected["severity"],
                    "rule": detected["rule"],
                    "risk_score": detected.get("score", 0),
                    "model_signals": detected.get("signals", []),
                    "agent_name": agent_name,
                    "session_file": fp.name,
                    "timestamp": ts or None,
                    "role": role,
                    "matched_text": str(needle)[:180],
                    "context": snippet[:900],
                })
    warning = sum(1 for h in hits if h["severity"] == "warning")
    info = sum(1 for h in hits if h["severity"] != "warning")
    return {
        "scanned_files": scanned_files,
        "total_hits": len(hits),
        "warning_hits": warning,
        "info_hits": info,
        "hits": hits,
    }


def _scan_agent_content_files(agent_name: str) -> tuple[list[dict[str, Any]], bool]:
    """Scan TOOLS.md, AGENTS.md, skills/*/SKILL.md. Returns (signals, missing_tools_md)."""
    base = Path(AGENTS_DIR) / resolve_agent_dir(agent_name)
    signals: list[dict[str, Any]] = []
    missing_tools = not (base / "TOOLS.md").is_file()

    files_to_scan: list[tuple[Path, str]] = []
    for n in ("TOOLS.md", "AGENTS.md"):
        p = base / n
        if p.is_file():
            files_to_scan.append((p, n))

    skills_dir = base / "skills"
    if skills_dir.is_dir():
        for sd in sorted(skills_dir.iterdir()):
            if not sd.is_dir():
                continue
            sm = sd / "SKILL.md"
            if sm.is_file():
                files_to_scan.append((sm, f"skills/{sd.name}/SKILL.md"))

    for fp, rel in files_to_scan:
        for h in _scan_text_file(fp):
            signals.append({
                "scope": "agent",
                "agent_name": agent_name,
                "global_source": None,
                "path": rel,
                **h,
            })
    return signals, missing_tools


def _global_skill_skill_md_path(source: str, skill_name: str) -> Path | None:
    if source == "shared":
        p = Path(SHARED_SKILLS_DIR) / skill_name / "SKILL.md"
    elif source == "global":
        p = Path(GLOBAL_SKILLS_DIR) / skill_name / "SKILL.md"
    else:
        return None
    return p if p.is_file() else None


def _scan_global_skill_content() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for src in gs.list_sources():
        source = src["source"]
        for sk in gs.list_skills(source):
            name = sk["name"]
            fp = _global_skill_skill_md_path(source, name)
            if fp is None:
                continue
            rel = f"{name}/SKILL.md"
            for h in _scan_text_file(fp):
                out.append({
                    "scope": "global_skill",
                    "agent_name": None,
                    "global_source": source,
                    "path": rel,
                    **h,
                })
    return out


def _collect_all_content_signals(agent_names: list[str]) -> list[dict[str, Any]]:
    """Sync: scan agents + global skills; cap total rows."""
    all_hits: list[dict[str, Any]] = []
    for an in agent_names:
        sigs, _ = _scan_agent_content_files(an)
        all_hits.extend(sigs)
    all_hits.extend(_scan_global_skill_content())
    return all_hits[:_MAX_TOTAL_SIGNALS]


def _external_sources() -> dict[str, str]:
    """Reference links used in security center."""
    return {
        "clawhub": "https://clawhub.ai/",
        "openclaw_configuration": "https://docs.openclaw.ai/gateway/configuration-reference",
        "virustotal": "https://www.virustotal.com/",
        "osv": "https://osv.dev/",
    }


def _skill_clawhub_url(skill_name: str) -> str:
    # Keep a stable fallback only; search query URL format may change.
    return "https://clawhub.ai/"


def _extract_links_from_text(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s)>\]\"]+", text)
    # common git shorthand
    github_short = re.findall(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b", text)
    for item in github_short:
        # avoid false positives from paths with dots/slashes by requiring one slash and no spaces
        if item.count("/") == 1 and not item.startswith(("http://", "https://")):
            urls.append(f"https://github.com/{item}")
    out: list[str] = []
    seen: set[str] = set()
    for u in urls:
        nu = u.strip().rstrip(".,);")
        if not nu or nu in seen:
            continue
        seen.add(nu)
        out.append(nu)
    return out[:8]


def _extract_skill_source_links(scope: str, agent_name: str | None, global_source: str | None, skill_name: str) -> dict[str, Any]:
    """Extract canonical links from SKILL.md content; fallback to ClawHub home."""
    skill_md: Path | None = None
    if scope == "agent" and agent_name:
        skill_md = Path(AGENTS_DIR) / resolve_agent_dir(agent_name) / "skills" / skill_name / "SKILL.md"
    elif scope == "global_skill" and global_source:
        skill_md = _global_skill_skill_md_path(global_source, skill_name)

    links: list[str] = []
    if skill_md and skill_md.is_file():
        try:
            text = skill_md.read_text(encoding="utf-8", errors="replace")
            links = _extract_links_from_text(text)
        except OSError:
            links = []

    # Prefer GitHub/npm/homepage-like URLs if present.
    preferred = None
    for u in links:
        ul = u.lower()
        if "github.com" in ul or "npmjs.com" in ul or "gitlab.com" in ul:
            preferred = u
            break
    if preferred is None and links:
        preferred = links[0]

    if preferred is None:
        preferred = _skill_clawhub_url(skill_name)

    return {
        "primary_link": preferred,
        "source_links": links,
    }


def _build_skill_supply_audit(
    agents_out: list[dict[str, Any]],
    global_sources: list[dict[str, Any]],
    content_signals: list[dict[str, Any]],
    virustotal: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate audit rows by installed skill (agent/global/shared)."""
    signal_index: dict[tuple[str, str | None, str | None, str], dict[str, int]] = {}
    for s in content_signals:
        scope = s.get("scope")
        path = str(s.get("path") or "")
        skill_name = None
        if scope == "agent" and path.startswith("skills/") and path.endswith("/SKILL.md"):
            parts = path.split("/")
            if len(parts) >= 3:
                skill_name = parts[1]
        elif scope == "global_skill" and path.endswith("/SKILL.md"):
            skill_name = path.split("/", 1)[0]
        if not skill_name:
            continue
        key = (scope, s.get("agent_name"), s.get("global_source"), skill_name)
        slot = signal_index.setdefault(key, {"warning": 0, "info": 0, "total": 0})
        sev = "warning" if s.get("severity") == "warning" else "info"
        slot[sev] += 1
        slot["total"] += 1

    vt_index: dict[tuple[str, str | None, str | None, str], dict[str, Any]] = {}
    for h in (virustotal.get("hits") or []):
        scope = h.get("scope")
        path = str(h.get("path") or "")
        skill_name = None
        if scope == "agent" and path.startswith("skills/") and path.endswith("/SKILL.md"):
            parts = path.split("/")
            if len(parts) >= 3:
                skill_name = parts[1]
        elif scope == "global_skill" and path.endswith("/SKILL.md"):
            skill_name = path.split("/", 1)[0]
        if not skill_name:
            continue
        key = (scope, h.get("agent_name"), h.get("global_source"), skill_name)
        vt_index[key] = {
            "malicious": int(h.get("malicious") or 0),
            "suspicious": int(h.get("suspicious") or 0),
            "link": h.get("link"),
            "sha256": h.get("sha256"),
        }

    local_rows: list[dict[str, Any]] = []
    for a in agents_out:
        for sk in a.get("local_skills") or []:
            key = ("agent", a.get("name"), None, sk["name"])
            sig = signal_index.get(key, {"warning": 0, "info": 0, "total": 0})
            vt = vt_index.get(key)
            src_links = _extract_skill_source_links("agent", a.get("name"), None, sk["name"])
            local_rows.append({
                "scope_level": "agent_local",
                "agent_name": a.get("name"),
                "global_source": None,
                "skill_name": sk["name"],
                "display_name": sk.get("display_name", sk["name"]),
                "file_count": sk.get("file_count", 0),
                "signal_warning": sig["warning"],
                "signal_info": sig["info"],
                "signal_total": sig["total"],
                "vt": vt,
                "primary_link": src_links["primary_link"],
                "source_links": src_links["source_links"],
            })

    global_rows: list[dict[str, Any]] = []
    for src in global_sources:
        source = src.get("source")
        for sk in src.get("skills") or []:
            key = ("global_skill", None, source, sk["name"])
            sig = signal_index.get(key, {"warning": 0, "info": 0, "total": 0})
            vt = vt_index.get(key)
            src_links = _extract_skill_source_links("global_skill", None, source, sk["name"])
            global_rows.append({
                "scope_level": "global_or_shared",
                "agent_name": None,
                "global_source": source,
                "skill_name": sk["name"],
                "display_name": sk.get("display_name", sk["name"]),
                "file_count": sk.get("file_count", 0),
                "signal_warning": sig["warning"],
                "signal_info": sig["info"],
                "signal_total": sig["total"],
                "vt": vt,
                "primary_link": src_links["primary_link"],
                "source_links": src_links["source_links"],
            })

    return {
        "local_agent_skills": local_rows,
        "global_or_shared_skills": global_rows,
    }


def _sha256_of_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            while True:
                chunk = f.read(1024 * 256)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _collect_virustotal_targets(agent_names: list[str]) -> list[dict[str, Any]]:
    """Collect key files for VT hash lookups."""
    targets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for an in agent_names:
        base = Path(AGENTS_DIR) / resolve_agent_dir(an)
        for rel in ("TOOLS.md", "AGENTS.md"):
            fp = base / rel
            if not fp.is_file():
                continue
            key = str(fp.resolve())
            if key in seen:
                continue
            seen.add(key)
            targets.append({
                "scope": "agent",
                "agent_name": an,
                "global_source": None,
                "path": rel,
                "abs_path": fp,
            })
        skills_dir = base / "skills"
        if skills_dir.is_dir():
            for sd in sorted(skills_dir.iterdir()):
                sm = sd / "SKILL.md"
                if not sm.is_file():
                    continue
                key = str(sm.resolve())
                if key in seen:
                    continue
                seen.add(key)
                targets.append({
                    "scope": "agent",
                    "agent_name": an,
                    "global_source": None,
                    "path": f"skills/{sd.name}/SKILL.md",
                    "abs_path": sm,
                })
    for src in gs.list_sources():
        source = src["source"]
        for sk in gs.list_skills(source):
            fp = _global_skill_skill_md_path(source, sk["name"])
            if fp is None:
                continue
            key = str(fp.resolve())
            if key in seen:
                continue
            seen.add(key)
            targets.append({
                "scope": "global_skill",
                "agent_name": None,
                "global_source": source,
                "path": f"{sk['name']}/SKILL.md",
                "abs_path": fp,
            })
    return targets[:_MAX_VT_FILES]


async def _fetch_virustotal(agent_names: list[str]) -> dict[str, Any]:
    key = (os.environ.get("VIRUSTOTAL_API_KEY") or "").strip()
    targets = _collect_virustotal_targets(agent_names)
    if not key:
        return {
            "enabled": False,
            "reason": "VIRUSTOTAL_API_KEY not configured",
            "scanned_files": 0,
            "hits": [],
        }
    if not targets:
        return {"enabled": True, "scanned_files": 0, "hits": []}

    headers = {"x-apikey": key}
    hits: list[dict[str, Any]] = []
    scanned = 0
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        for t in targets:
            sha256 = _sha256_of_file(t["abs_path"])
            if not sha256:
                continue
            scanned += 1
            url = f"https://www.virustotal.com/api/v3/files/{sha256}"
            try:
                resp = await client.get(url, headers=headers)
            except Exception:
                continue
            if resp.status_code == 404:
                continue
            if resp.status_code != 200:
                continue
            try:
                data = resp.json().get("data", {})
                stats = (data.get("attributes", {}) or {}).get("last_analysis_stats", {}) or {}
                malicious = int(stats.get("malicious", 0) or 0)
                suspicious = int(stats.get("suspicious", 0) or 0)
            except Exception:
                continue
            if malicious <= 0 and suspicious <= 0:
                continue
            hits.append({
                "scope": t["scope"],
                "agent_name": t["agent_name"],
                "global_source": t["global_source"],
                "path": t["path"],
                "sha256": sha256,
                "malicious": malicious,
                "suspicious": suspicious,
                "link": f"https://www.virustotal.com/gui/file/{sha256}",
            })
    return {
        "enabled": True,
        "scanned_files": scanned,
        "hits": hits,
    }


def _frontend_direct_npm_dependencies() -> list[dict[str, str]]:
    lock = Path(__file__).resolve().parents[3] / "frontend" / "package-lock.json"
    if not lock.is_file():
        return []
    try:
        data = json.loads(lock.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    root_pkg = ((data.get("packages") or {}).get("") or {})
    root_deps = root_pkg.get("dependencies") or {}
    out: list[dict[str, str]] = []
    for name in sorted(root_deps.keys()):
        node = ((data.get("packages") or {}).get(f"node_modules/{name}") or {})
        version = (node.get("version") or "").strip()
        if not version:
            continue
        out.append({"name": name, "version": version})
        if len(out) >= _MAX_OSV_DIRECT_DEPS:
            break
    return out


def _deps_from_package_json(path: Path) -> list[dict[str, str]]:
    """Collect concrete npm deps from one package.json (only exact versions)."""
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    out: list[dict[str, str]] = []
    for sec in ("dependencies", "optionalDependencies"):
        block = data.get(sec) or {}
        if not isinstance(block, dict):
            continue
        for name, version in block.items():
            v = str(version or "").strip()
            # OSV version query prefers concrete versions (skip ranges/tags)
            if not v or any(ch in v for ch in "^~*><=| "):
                continue
            out.append({"name": str(name), "version": v})
    return out


def _skill_direct_npm_dependencies() -> dict[str, list[dict[str, str]]]:
    """Collect npm deps from global/shared skill package.json files."""
    out: dict[str, list[dict[str, str]]] = {}
    for source_key, base in (("global_skills", Path(GLOBAL_SKILLS_DIR)), ("shared_skills", Path(SHARED_SKILLS_DIR))):
        rows: list[dict[str, str]] = []
        if not base.is_dir():
            out[source_key] = rows
            continue
        for sk in sorted(base.iterdir()):
            if not sk.is_dir():
                continue
            pkg = sk / "package.json"
            for dep in _deps_from_package_json(pkg):
                rows.append({
                    "name": dep["name"],
                    "version": dep["version"],
                    "component": sk.name,
                    "scope": source_key,
                })
                if len(rows) >= _MAX_OSV_DIRECT_DEPS:
                    break
            if len(rows) >= _MAX_OSV_DIRECT_DEPS:
                break
        out[source_key] = rows
    return out


def _openclaw_runtime_npm_dependencies() -> list[dict[str, str]]:
    """Best-effort: collect deps near openclaw.json (if a package.json exists there)."""
    cfg = Path(OPENCLAW_CONFIG_PATH)
    candidates = [
        cfg.parent / "package.json",
        cfg.parent.parent / "package.json" if cfg.parent.parent else None,
    ]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for c in candidates:
        if not c or not c.is_file():
            continue
        for dep in _deps_from_package_json(c):
            k = f"{dep['name']}@{dep['version']}"
            if k in seen:
                continue
            seen.add(k)
            rows.append({
                "name": dep["name"],
                "version": dep["version"],
                "component": str(c.parent),
                "scope": "openclaw_runtime",
            })
            if len(rows) >= _MAX_OSV_DIRECT_DEPS:
                return rows
    return rows


def _collect_npm_dependency_sets() -> dict[str, list[dict[str, str]]]:
    return {
        "frontend": _frontend_direct_npm_dependencies(),
        "openclaw_runtime": _openclaw_runtime_npm_dependencies(),
        **_skill_direct_npm_dependencies(),
    }


async def _fetch_osv_npm_vulns() -> dict[str, Any]:
    dep_sets = _collect_npm_dependency_sets()
    deps = []
    for scope, rows in dep_sets.items():
        for d in rows:
            deps.append({
                "name": d["name"],
                "version": d["version"],
                "scope": scope,
                "component": d.get("component"),
            })
    deps = deps[:_MAX_OSV_QUERY_PACKAGES]
    if not deps:
        return {"checked_packages": 0, "vulnerabilities": [], "checked_by_scope": {}}
    queries = [
        {"package": {"name": d["name"], "ecosystem": "npm"}, "version": d["version"]}
        for d in deps
    ]
    payload = {"queries": queries}
    vulns: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post("https://api.osv.dev/v1/querybatch", json=payload)
        if resp.status_code != 200:
            return {"checked_packages": len(deps), "vulnerabilities": [], "checked_by_scope": {}}
        results = (resp.json() or {}).get("results") or []
    except Exception:
        return {"checked_packages": len(deps), "vulnerabilities": [], "checked_by_scope": {}}

    for idx, item in enumerate(results):
        ds = deps[idx]
        for v in (item.get("vulns") or []):
            aliases = v.get("aliases") or []
            fixed = None
            for aff in (v.get("affected") or []):
                for r in (aff.get("ranges") or []):
                    for ev in (r.get("events") or []):
                        if ev.get("fixed"):
                            fixed = ev.get("fixed")
                            break
                    if fixed:
                        break
                if fixed:
                    break
            vulns.append({
                "package": ds["name"],
                "version": ds["version"],
                "scope": ds.get("scope"),
                "component": ds.get("component"),
                "id": v.get("id"),
                "aliases": aliases[:6],
                "summary": (v.get("summary") or "")[:220] or None,
                "details": (v.get("details") or "")[:320] or None,
                "fixed_version": fixed,
                "link": f"https://osv.dev/vulnerability/{v.get('id')}" if v.get("id") else "https://osv.dev/",
            })
    checked_by_scope: dict[str, int] = {}
    for d in deps:
        sc = d.get("scope") or "unknown"
        checked_by_scope[sc] = checked_by_scope.get(sc, 0) + 1
    return {"checked_packages": len(deps), "vulnerabilities": vulns, "checked_by_scope": checked_by_scope}


def _llm_flags() -> dict[str, Any]:
    from .config import read_config

    cfg = read_config()
    llm = cfg.get("llm", {})
    default = llm.get("default", {})
    overrides = llm.get("overrides") or {}
    purposes = []
    for purpose, oc in overrides.items():
        if isinstance(oc, dict) and (oc.get("api_key") or "").strip():
            purposes.append(purpose)
    return {
        "default_has_api_key": bool((default.get("api_key") or "").strip()),
        "override_purposes_with_api_key": sorted(purposes),
        "data_dir": str(DATA_DIR),
    }


def _build_findings(
    cors_all: bool,
    gateway_token_set: bool,
    secret_var_count: int,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if cors_all:
        findings.append({
            "severity": "warning",
            "code": "CORS_ALLOW_ALL",
            "message": "ALLOWED_ORIGINS is * — any origin can call this API from a browser.",
        })
    if not gateway_token_set:
        findings.append({
            "severity": "info",
            "code": "GATEWAY_TOKEN_UNSET",
            "message": "GATEWAY_TOKEN is empty — outbound gateway calls may fail or be rejected.",
        })
    if secret_var_count > 0:
        findings.append({
            "severity": "info",
            "code": "SECRET_VARIABLES_PRESENT",
            "message": f"{secret_var_count} variable(s) marked as type secret (values never shown in this report).",
        })
    return findings


async def build_audit_report() -> dict[str, Any]:
    """Aggregate read-only audit data for the Security Center."""
    generated_at = datetime.now(timezone.utc).isoformat()

    cors_all, origin_count = _cors_allow_all()
    gateway_token_set = bool((GATEWAY_TOKEN or "").strip())

    openclaw_path = Path(OPENCLAW_CONFIG_PATH)
    openclaw = _openclaw_preview(openclaw_path)

    agents_raw = await scanner.list_agents_async()
    agents_out: list[dict[str, Any]] = []
    for a in agents_raw:
        name = a["name"]
        agent_id = await version_db.get_or_create_agent(name)
        derivation = await version_db.get_derivation_by_agent_id(agent_id)
        bp_name = None
        if derivation:
            bp = await version_db.get_blueprint(derivation["blueprint_id"])
            bp_name = bp["name"] if bp else None

        skill_rows = await _agent_skill_rows(name)
        total_files = sum(s["file_count"] for s in skill_rows)

        agents_out.append({
            "name": name,
            "display_name": a.get("display_name"),
            "id": agent_id,
            "blueprint_name": bp_name,
            "host_path": a.get("host_path"),
            "policy_files": _policy_files(name),
            "local_skills": skill_rows,
            "local_skill_count": len(skill_rows),
            "local_skill_file_total": total_files,
        })

    variables_raw = await version_db.list_variables()
    masked = [variable_service.mask_variable(dict(v)) for v in variables_raw]
    by_type: dict[str, int] = {}
    by_scope: dict[str, int] = {}
    for v in variables_raw:
        t = v.get("type") or "text"
        by_type[t] = by_type.get(t, 0) + 1
        sc = v.get("scope") or "global"
        by_scope[sc] = by_scope.get(sc, 0) + 1
    secret_count = sum(1 for v in variables_raw if v.get("type") == "secret")

    var_entries = []
    for v in masked:
        var_entries.append({
            "id": v["id"],
            "name": v["name"],
            "type": v.get("type"),
            "scope": v.get("scope"),
            "agent_id": v.get("agent_id"),
            "description": (v.get("description") or "")[:200] or None,
        })

    global_sources = await _global_source_rows()

    agent_name_list = [a["name"] for a in agents_out]
    content_signals = await asyncio.to_thread(_collect_all_content_signals, agent_name_list)
    session_risks = await asyncio.to_thread(_scan_session_risks, agent_name_list)
    virustotal = await _fetch_virustotal(agent_name_list)
    osv_npm = await _fetch_osv_npm_vulns()
    skill_supply_audit = _build_skill_supply_audit(
        agents_out=agents_out,
        global_sources=global_sources,
        content_signals=content_signals,
        virustotal=virustotal,
    )

    agents_missing_tools = sum(
        1 for a in agents_out if not a["policy_files"].get("TOOLS.md", False)
    )
    content_warning_hits = sum(1 for s in content_signals if s.get("severity") == "warning")

    findings = _build_findings(cors_all, gateway_token_set, secret_count)

    if (
        openclaw.get("parsed")
        and openclaw.get("agents_registry_declared")
        and openclaw.get("agents_in_registry_count", 0) != len(agents_out)
    ):
        findings.append({
            "severity": "info",
            "code": "OPENCLAW_REGISTRY_COUNT_MISMATCH",
            "message": (
                f"openclaw.json agents.list has {openclaw['agents_in_registry_count']} entries, "
                f"but this dashboard scanned {len(agents_out)} workspace(s). "
                "This may be normal if workspaces are not all registered."
            ),
        })
    if agents_missing_tools > 0:
        findings.append({
            "severity": "warning",
            "code": "MISSING_TOOLS_MD",
            "message": f"{agents_missing_tools} agent workspace(s) have no TOOLS.md at the workspace root.",
        })
    if content_warning_hits > 0:
        findings.append({
            "severity": "info",
            "code": "CONTENT_HEURISTIC_HITS",
            "message": (
                f"{content_warning_hits} heuristic match(es) with severity 'warning' in scanned markdown "
                "(see Content scan). Review context; not all matches are vulnerabilities."
            ),
        })
    if (session_risks.get("warning_hits") or 0) > 0:
        findings.append({
            "severity": "warning",
            "code": "SESSION_SENSITIVE_ACTIONS",
            "message": (
                f"Detected {session_risks['warning_hits']} high-risk session action(s) "
                "(privilege escalation, secrets exposure, plugin/skill installs)."
            ),
        })
    if (session_risks.get("info_hits") or 0) > 0:
        findings.append({
            "severity": "info",
            "code": "SESSION_SECURITY_SIGNALS",
            "message": f"Detected {session_risks['info_hits']} additional session security signal(s).",
        })
    if (virustotal.get("hits") or []):
        findings.append({
            "severity": "warning",
            "code": "VIRUSTOTAL_HITS",
            "message": f"VirusTotal reported suspicious/malicious results for {len(virustotal['hits'])} scanned file(s).",
        })
    if (osv_npm.get("vulnerabilities") or []):
        by_scope = osv_npm.get("checked_by_scope") or {}
        scope_summary = ", ".join(f"{k}={v}" for k, v in sorted(by_scope.items())) or "n/a"
        findings.append({
            "severity": "warning",
            "code": "NPM_KNOWN_VULNERABILITIES",
            "message": (
                f"OSV found {len(osv_npm['vulnerabilities'])} known vulnerability record(s) "
                f"across npm dependency scopes ({scope_summary})."
            ),
        })
    if any(v.get("scope") in {"global_skills", "shared_skills"} for v in (osv_npm.get("vulnerabilities") or [])):
        findings.append({
            "severity": "warning",
            "code": "SKILL_NPM_VULNERABILITIES",
            "message": "Known npm vulnerabilities were detected in global/shared skill dependencies.",
        })
    if any(v.get("scope") == "openclaw_runtime" for v in (osv_npm.get("vulnerabilities") or [])):
        findings.append({
            "severity": "warning",
            "code": "OPENCLAW_RUNTIME_NPM_VULNERABILITIES",
            "message": "Known npm vulnerabilities were detected near OpenClaw runtime dependencies.",
        })
    malware_like = 0
    for v in (osv_npm.get("vulnerabilities") or []):
        text = f"{v.get('summary') or ''} {v.get('details') or ''}".lower()
        if any(k in text for k in ("malware", "backdoor", "trojan", "credential theft", "exfiltrat", "typosquat")):
            malware_like += 1
    if malware_like > 0:
        findings.append({
            "severity": "warning",
            "code": "NPM_POSSIBLE_MALICIOUS_PACKAGES",
            "message": f"{malware_like} npm vulnerability record(s) include malware-like indicators; review package provenance immediately.",
        })

    for rec in openclaw.get("security_recommendations") or []:
        if rec.get("severity") == "warning":
            rid = rec.get("id", "UNKNOWN")
            code = rid if str(rid).startswith("OPENCLAW_") else f"OPENCLAW_{rid}"
            findings.append({
                "severity": "warning",
                "code": code,
                "message": f"openclaw.json: {rid} — see OpenClaw security recommendations below.",
            })

    findings.sort(key=lambda f: (0 if f.get("severity") == "warning" else 1, f.get("code", "")))

    fw = sum(1 for f in findings if f.get("severity") == "warning")
    fi = sum(1 for f in findings if f.get("severity") == "info")
    cw = sum(1 for s in content_signals if s.get("severity") == "warning")
    ci = sum(1 for s in content_signals if s.get("severity") == "info")

    return {
        "generated_at": generated_at,
        "summary": {
            "agents_scanned": len(agents_out),
            "global_skill_sources": len(global_sources),
            "findings_warning": fw,
            "findings_info": fi,
            "content_hits_total": len(content_signals),
            "content_hits_warning": cw,
            "content_hits_info": ci,
            "agents_missing_tools_md": agents_missing_tools,
        },
        "dashboard": {
            "cors_allow_all": cors_all,
            "allowed_origins_count": origin_count,
            "gateway_url": GATEWAY_URL,
            "gateway_token_configured": gateway_token_set,
            "agents_dir": AGENTS_DIR,
            "global_skills_dir": GLOBAL_SKILLS_DIR,
            "shared_skills_dir": SHARED_SKILLS_DIR,
            "openclaw_config": openclaw,
        },
        "llm_settings": _llm_flags(),
        "external_intel": {
            "sources": _external_sources(),
            "clawhub": {
                "source_url": "https://clawhub.ai/",
                "notes": "Use ClawHub search to verify skill provenance/version context manually.",
            },
            "virustotal": virustotal,
            "osv_npm": osv_npm,
        },
        "agents": agents_out,
        "global_skill_sources": global_sources,
        "skill_supply_audit": skill_supply_audit,
        "content_signals": content_signals,
        "session_risks": session_risks,
        "variables": {
            "total": len(variables_raw),
            "by_type": by_type,
            "by_scope": by_scope,
            "entries": var_entries,
        },
        "findings": findings,
    }
