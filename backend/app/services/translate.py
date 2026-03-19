"""Translation service — calls OpenAI-compatible API to translate content."""
import json
from pathlib import Path

import httpx

from ..config import AGENTS_DIR, DATA_DIR, resolve_agent_dir
from .config import get_llm_config


def _translation_path(agent_name: str, rel_path: str) -> Path:
    """Return the path where the translated file is stored."""
    return Path(DATA_DIR) / agent_name / rel_path


def get_translation(agent_name: str, rel_path: str) -> dict | None:
    """Read a previously saved translation."""
    trans_path = _translation_path(agent_name, rel_path)
    if not trans_path.exists():
        return None
    try:
        content = trans_path.read_text(encoding="utf-8", errors="replace")
        return {
            "path": rel_path,
            "name": trans_path.name,
            "content": content,
            "language": "markdown",
        }
    except Exception:
        return None


def translation_exists(agent_name: str, rel_path: str) -> bool:
    return _translation_path(agent_name, rel_path).exists()


async def translate_file(agent_name: str, rel_path: str) -> dict:
    """Translate a file using configured OpenAI-compatible API."""
    # Read original file
    original_path = Path(AGENTS_DIR) / resolve_agent_dir(agent_name) / rel_path
    if not original_path.exists():
        raise FileNotFoundError(f"File not found: {rel_path}")

    content = original_path.read_text(encoding="utf-8", errors="replace")

    # Read config
    config = get_llm_config("translation")
    if not config.get("openai_base_url") or not config.get("api_key"):
        raise ValueError("LLM API not configured. Please set up in Settings.")

    base_url = config["openai_base_url"].rstrip("/")
    api_key = config["api_key"]
    model = config.get("model_name", "gpt-4o-mini")

    # Call OpenAI-compatible API
    prompt = (
        "请将以下内容翻译为中文。保留原始的 Markdown 格式、代码块和链接。"
        "只输出翻译后的内容，不要添加任何解释。\n\n"
        f"{content}"
    )

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是一个专业的技术文档翻译器。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    translated = data["choices"][0]["message"]["content"]

    # Save translation
    trans_path = _translation_path(agent_name, rel_path)
    trans_path.parent.mkdir(parents=True, exist_ok=True)
    trans_path.write_text(translated, encoding="utf-8")

    return {
        "path": rel_path,
        "name": Path(rel_path).name,
        "content": translated,
        "language": "markdown",
    }
