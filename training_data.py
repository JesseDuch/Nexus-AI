"""Public dataset sources for future RL/tool-orchestration training (roadmap 3.2).

Fetches real prompt→tool examples from public sources when network allows, with
graceful offline fallback. Records are persisted as JSONL under data/training/.
Each record: {"prompt", "action", "source"} — the exact shape the TF-Agents
trainer consumes.
"""
import json
from pathlib import Path

import httpx

from .config import get_settings

settings = get_settings()

_TIMEOUT = httpx.Timeout(connect=8.0, read=30.0, write=10.0, pool=5.0)

# Curated offline seed set (always available; network sources extend it).
_SEED: list[dict] = [
    {"prompt": "compute the first 10 fibonacci numbers", "action": "code_exec", "source": "seed"},
    {"prompt": "plot y = sin(x) from 0 to 2pi", "action": "code_exec", "source": "seed"},
    {"prompt": "draw a serene japanese garden at sunset", "action": "image_gen", "source": "seed"},
    {"prompt": "generate an image of a futuristic city at night", "action": "image_gen", "source": "seed"},
    {"prompt": "generate a video of waves on a beach", "action": "video_gen", "source": "seed"},
    {"prompt": "make a video of a rotating cube", "action": "video_gen", "source": "seed"},
    {"prompt": "explain the difference between TCP and UDP", "action": "chat", "source": "seed"},
    {"prompt": "write a FastAPI endpoint that validates emails", "action": "chat", "source": "seed"},
]


def dataset_dir() -> Path:
    d = Path(settings.media_dir).parent / "training"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def fetch_stackoverflow_python(limit: int = 25) -> list[dict]:
    """Pull recent Python Q&A titles from the public Stack Exchange API — they
    map naturally to the code_exec action."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                "https://api.stackexchange.com/2.3/questions",
                params={
                    "site": "stackoverflow",
                    "tagged": "python",
                    "sort": "votes",
                    "pagesize": min(limit, 100),
                    "filter": "withbody",
                },
            )
            items = resp.json().get("items", [])
            return [
                {"prompt": it.get("title", ""), "action": "code_exec", "source": "stackexchange"}
                for it in items
                if it.get("title")
            ]
    except Exception:
        return []


async def build_dataset(include_network: bool = True) -> dict:
    """Assemble the routing-training dataset; persist as JSONL."""
    records = list(_SEED)
    network_count = 0
    if include_network:
        so = await fetch_stackoverflow_python()
        network_count = len(so)
        records.extend(so)

    out = dataset_dir() / "router_dataset.jsonl"
    with out.open("w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return {
        "records": len(records),
        "network_records": network_count,
        "seed_records": len(_SEED),
        "path": str(out),
    }
