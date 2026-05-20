"""data-hub-ashgr-denver CLI — promote, index, and search ASHGR Denver documents.

All content is promoted from research-agent, newsletter-agent, and project-ashgr-denver.
Members directory is always private and gitignored. Everything else defaults to public.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import click
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent
_LANCEDB_DIR = _REPO_ROOT / "data" / "lancedb"
_LACIE_RAW = Path("/Volumes/LaCie/data-hub/ahsgr/journals")

_ALWAYS_PRIVATE = {"members"}
_VALID_TIERS = {"public", "private"}
_VALID_TOPICS = {
    "journals/clues",
    "journals/journal",
    "journals/work-papers",
    "journals/jugendezeitung",
    "journals/newsletter",
    "board/roster",
    "board/meetings",
    "members",
    "genealogy",
    "research",
}

def _validate_topic(topic: str) -> None:
    if topic not in _VALID_TOPICS:
        raise click.BadParameter(f"Unknown topic '{topic}'. Valid: {sorted(_VALID_TOPICS)}")

_SERIES_MAP = {
    "CLUES": "journals/clues",
    "Journal": "journals/journal",
    "WorkPaper": "journals/work-papers",
    "JugendZeitung": "journals/jugendezeitung",
    "Newsletter": "journals/newsletter",
}


# ── Frontmatter helpers ──────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, parts[2].lstrip("\n")


def _inject_frontmatter(meta: dict, body: str) -> str:
    fm = yaml.dump(meta, default_flow_style=False, allow_unicode=True).strip()
    return f"---\n{fm}\n---\n\n{body}"


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s_-]+", "-", text)[:80]


def _enforce_tier(topic: str, requested_tier: str) -> str:
    root = topic.split("/")[0]
    if root in _ALWAYS_PRIVATE:
        if requested_tier != "private":
            log.warning("Topic %s is always private — overriding tier to private", topic)
        return "private"
    return requested_tier


# ── CLI ──────────────────────────────────────────────────────────────────────

@click.group()
def cli() -> None:
    """data-hub-ashgr-denver: promote, index, and search ASHGR Denver documents."""


@cli.command()
@click.argument("src", type=click.Path(exists=True, path_type=Path))
@click.option("--topic", required=True, help="Topic path, e.g. journals/clues")
@click.option("--tier", default="public", type=click.Choice(["public", "private"]))
@click.option("--source-agent", default="", help="Agent that produced this file")
@click.option("--title", default="", help="Override title (default: from frontmatter or filename)")
@click.option("--year", default="", help="Publication year (for journal articles)")
@click.option("--series", default="", help="Journal series slug")
@click.option("--tags", default="", help="Comma-separated tags")
def promote(
    src: Path,
    topic: str,
    tier: str,
    source_agent: str,
    title: str,
    year: str,
    series: str,
    tags: str,
) -> None:
    """Promote a markdown or CSV file into the hub taxonomy."""
    _validate_topic(topic)
    tier = _enforce_tier(topic, tier)
    dest_dir = _REPO_ROOT / topic
    dest_dir.mkdir(parents=True, exist_ok=True)

    text = src.read_text(encoding="utf-8", errors="replace")
    existing_meta, body = _parse_frontmatter(text)

    resolved_title = title or existing_meta.get("title") or src.stem.replace("-", " ").title()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    meta: dict = {
        "title": resolved_title,
        "topic": topic,
        "tier": tier,
        "source_agent": source_agent or existing_meta.get("source_agent", ""),
        "source_path": str(src),
        "promoted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if year:
        meta["year"] = year
    if series:
        meta["series"] = series
    if tag_list:
        meta["tags"] = tag_list

    slug = _slugify(resolved_title) or _slugify(src.stem)
    dest = dest_dir / f"{slug}.md"
    dest.write_text(_inject_frontmatter(meta, body or text), encoding="utf-8")
    log.info("✓ promoted → %s (%s)", dest.relative_to(_REPO_ROOT), tier)


@cli.command()
def build() -> None:
    """Rebuild the LanceDB index from all promoted documents."""
    try:
        import lancedb
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        log.error("Missing dep: %s — run `make install`", e)
        raise SystemExit(1)

    _LANCEDB_DIR.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(_LANCEDB_DIR))
    model = SentenceTransformer("all-MiniLM-L6-v2")

    docs = []
    for md in _REPO_ROOT.rglob("*.md"):
        # Skip index files, CLAUDE.md, raw/, members/ (gitignored but may exist locally)
        rel = md.relative_to(_REPO_ROOT)
        parts = rel.parts
        if parts[0] in ("raw", "members", ".git") or md.name in ("CLAUDE.md", "HEARTBEAT.md", "README.md"):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        meta, body = _parse_frontmatter(text)
        content = body.strip() or text.strip()
        if len(content) < 50:
            continue
        docs.append({
            "path": str(rel),
            "title": meta.get("title", md.stem),
            "topic": meta.get("topic", str(parts[0])),
            "tier": meta.get("tier", "public"),
            "year": str(meta.get("year", "")),
            "series": str(meta.get("series", "")),
            "tags": ", ".join(meta.get("tags", [])),
            "text": content[:8000],
            "vector": model.encode(content[:2000]).tolist(),
        })

    if not docs:
        log.warning("No documents found to index.")
        return

    import pandas as pd
    df = pd.DataFrame(docs)
    table_name = "ashgr_denver"
    if table_name in db.table_names():
        db.drop_table(table_name)
    db.create_table(table_name, data=df)
    log.info("✓ Indexed %d documents → %s", len(docs), _LANCEDB_DIR)


@cli.command()
@click.argument("query")
@click.option("--limit", default=10, show_default=True)
@click.option("--topic", default="", help="Filter by topic prefix")
def search(query: str, limit: int, topic: str) -> None:
    """Semantic search across the hub."""
    try:
        import lancedb
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        log.error("Missing dep: %s — run `make install`", e)
        raise SystemExit(1)

    if not _LANCEDB_DIR.exists():
        log.error("No index found — run `make build` first.")
        raise SystemExit(1)

    db = lancedb.connect(str(_LANCEDB_DIR))
    if "ashgr_denver" not in db.table_names():
        log.error("Table ashgr_denver not found — run `make build` first.")
        raise SystemExit(1)

    model = SentenceTransformer("all-MiniLM-L6-v2")
    vec = model.encode(query).tolist()
    table = db.open_table("ashgr_denver")
    results = table.search(vec).limit(limit * 3).to_pandas()

    if topic:
        results = results[results["topic"].str.startswith(topic)]
    results = results.head(limit)

    for _, row in results.iterrows():
        print(f"\n[{row['topic']}] {row['title']} ({row['year']})")
        print(f"  {row['path']}")
        print(f"  {row['text'][:200].strip()}...")


@cli.command()
@click.argument("question")
@click.option("--claude", is_flag=True, help="Use Claude instead of Ollama (public content only)")
@click.option("--limit", default=5, show_default=True)
def query(question: str, claude: bool, limit: int) -> None:
    """RAG query against indexed documents."""
    try:
        import lancedb
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        log.error("Missing dep: %s", e)
        raise SystemExit(1)

    if not _LANCEDB_DIR.exists():
        log.error("No index — run `make build` first.")
        raise SystemExit(1)

    db = lancedb.connect(str(_LANCEDB_DIR))
    if "ashgr_denver" not in db.table_names():
        log.error("Table not found — run `make build`.")
        raise SystemExit(1)

    model = SentenceTransformer("all-MiniLM-L6-v2")
    vec = model.encode(question).tolist()
    table = db.open_table("ashgr_denver")
    rows = table.search(vec).limit(limit).to_pandas()

    context = "\n\n---\n\n".join(
        f"[{r['topic']}] {r['title']}\n{r['text'][:1500]}" for _, r in rows.iterrows()
    )
    prompt = f"Answer the following question using only the provided context.\n\nQuestion: {question}\n\nContext:\n{context}"

    if claude:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        print(msg.content[0].text)
    else:
        import subprocess
        result = subprocess.run(
            ["ollama", "run", "llama3.2", prompt],
            capture_output=True, text=True, timeout=120,
        )
        print(result.stdout or result.stderr)


@cli.command()
def stats() -> None:
    """Show document counts per topic."""
    counts: dict[str, int] = {}
    total = 0
    for md in _REPO_ROOT.rglob("*.md"):
        rel = md.relative_to(_REPO_ROOT)
        parts = rel.parts
        if not parts:
            continue
        if parts[0] in ("raw", ".git") or md.name in ("CLAUDE.md", "HEARTBEAT.md", "README.md"):
            continue
        if len(parts) >= 2:
            key = f"{parts[0]}/{parts[1]}" if parts[1] != md.name else parts[0]
        else:
            key = parts[0]
        counts[key] = counts.get(key, 0) + 1
        total += 1

    print(f"\ndata-hub-ashgr-denver stats ({total} documents)\n")
    for topic in sorted(counts):
        print(f"  {topic:<35} {counts[topic]:>4}")
    print()

    indexed = _LANCEDB_DIR.exists()
    print(f"  LanceDB index: {'✓ exists' if indexed else '✗ not built — run make build'}")
    print()


@cli.command("index-raw")
def index_raw() -> None:
    """Scan LaCie raw PDF collection → raw/INDEX.md."""
    if not _LACIE_RAW.exists():
        log.error("LaCie not mounted — expected %s", _LACIE_RAW)
        raise SystemExit(1)

    pdfs = sorted(_LACIE_RAW.glob("*.pdf"))
    log.info("Found %d PDFs in %s", len(pdfs), _LACIE_RAW)

    series_counts: dict[str, int] = {}
    year_range: dict[str, list[int]] = {}
    issue_range: dict[str, list[int]] = {}

    for pdf in pdfs:
        name = pdf.stem
        for series_key, topic in _SERIES_MAP.items():
            if series_key in name:
                series_counts[topic] = series_counts.get(topic, 0) + 1
                years = re.findall(r"\d{4}", name)
                if years:
                    y = int(years[0])
                    yr = year_range.setdefault(topic, [y, y])
                    yr[0] = min(yr[0], y)
                    yr[1] = max(yr[1], y)
                else:
                    # Vol/No numbered series — track issue numbers
                    nos = re.findall(r"No(\d+)", name)
                    vols = re.findall(r"Vol(\d+)", name)
                    n = int(nos[0]) if nos else (int(vols[0]) if vols else 0)
                    if n:
                        ir = issue_range.setdefault(topic, [n, n])
                        ir[0] = min(ir[0], n)
                        ir[1] = max(ir[1], n)
                break

    lines = [
        "# ASHGR Raw PDF Index\n",
        f"**Source:** {_LACIE_RAW}\n",
        f"**Total PDFs:** {len(pdfs)}\n",
        f"**Generated:** {datetime.now(timezone.utc).date()}\n\n",
        "## By Series\n\n",
        "| Series (topic) | Count | Range |\n",
        "|---|---|---|\n",
    ]
    for topic in sorted(series_counts):
        if topic in year_range:
            yr = year_range[topic]
            rng = f"{yr[0]}–{yr[1]}"
        elif topic in issue_range:
            ir = issue_range[topic]
            rng = f"No.{ir[0]}–No.{ir[1]}"
        else:
            rng = "—"
        lines.append(f"| {topic} | {series_counts[topic]} | {rng} |\n")

    out = _REPO_ROOT / "raw" / "INDEX.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("".join(lines), encoding="utf-8")
    log.info("✓ Wrote %s", out)


if __name__ == "__main__":
    cli()
