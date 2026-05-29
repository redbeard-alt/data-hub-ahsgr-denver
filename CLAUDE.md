# CLAUDE.md — data-hub-ashgr-denver

ASHGR North Denver Chapter archive and shared research hub. Promotes from research-agent,
newsletter-agent, and project-ashgr-denver. Feeds a single LanceDB index for RAG search
across all chapter-relevant content. Multiple agents pull from this hub.

**BJH raw source:** `/Volumes/BJH/data-hub/ahsgr/` — 462 PDFs, 1.8GB, 5 series (1971–present).
**BJH must be mounted** for `make index-raw` and `make sync-lacie`.

## Architecture Position

```
BJH/data-hub/ahsgr/journals/   ← 462 raw PDFs (source of truth, read-only)
project-ashgr-denver/            ← roster/officer index CSV, MCP server
research-agent/                  ← web research, Perplexity runs
newsletter-agent/                ← chapter newsletter drafts
        ↓ promote
data-hub-ashgr-denver/           ← curated editorial layer (this repo)
        ↓ build
data/lancedb/                    ← LanceDB index (local, gitignored)
```

## Taxonomy

```
journals/
  clues/           ← AHSGR CLUES newsletter (genealogy tips, 1973–)
  journal/         ← Main AHSGR Journal (flagship publication)
  work-papers/     ← Early work papers (1971–1977, founding era)
  jugendezeitung/  ← JugendZeitung (German-language youth publication)
  newsletter/      ← Chapter/national newsletters
board/
  roster/          ← Officer+board records (CSV from project-ashgr-denver)
  meetings/        ← Meeting notes, agendas
members/           ← Member directory, profiles (ALWAYS PRIVATE — gitignored)
genealogy/         ← Germans from Russia genealogy research
research/          ← Shared docs pulled from data-hub (genealogy/, american-history/)
raw/               ← Source PDFs (gitignored — live on BJH)
```

## Sensitivity Tiers

| Tier | Content | Notes |
|---|---|---|
| `public` | journals/, board/roster, board/meetings, genealogy/, research/ | Cloud-safe |
| `private` | members/ | Ollama only, never committed |

**Always private:** `members/`
**Default public:** everything else in this hub

## CLI

```bash
python cli.py promote /path/to/file.md --topic journals/clues --tier public
python cli.py build
python cli.py search "volga german settlement patterns"
python cli.py query "who was newsletter editor in 1985?"
python cli.py stats
python cli.py index-raw          # scan LaCie PDFs → raw/INDEX.md (LaCie required)
```

## Makefile shortcuts

```bash
make install
make promote SRC="..." TOPIC="journals/clues"
make build
make search QUERY="..."
make query Q="..."
make sync-lacie          # rsync promoted docs → BJH (BJH required)
make index-raw           # scan LaCie raw PDFs → INDEX.md
make sync-data-hub       # pull shared research from ~/Laboratory/data-hub
```

## Multi-Agent Access

Any agent can promote here via subprocess:

```python
import subprocess
subprocess.run([
    str(Path.home() / "Laboratory/data-hub-ashgr-denver/.venv/bin/python"),
    str(Path.home() / "Laboratory/data-hub-ashgr-denver/cli.py"),
    "promote", str(src_path),
    "--topic", "journals/clues",
    "--source-agent", "research-agent",
])
```

## Frontmatter Standard

```yaml
---
title: Document Title
topic: journals/clues
tier: public
series: clues
year: 1985
source_agent: research-agent
source_path: /Volumes/BJH/data-hub/ahsgr/journals/AHSGR-CLUES-1985-pt1.pdf
promoted_at: 2026-05-19T00:00:00Z
tags: [clues, 1985, genealogy]
---
```

## OFF-LIMITS RULES

1. **Never commit audio or video** — markdown and CSV only
2. **Never commit raw PDFs** — `raw/` is gitignored; source lives on LaCie
3. **Never commit members/** — always private, gitignored
4. **LanceDB index is local only** — `data/lancedb/` gitignored; rebuild via `make build`
5. **Never override tier on members/** — always private

## Claude Skills

Shared skills are served via `additionalDirectories` from `config-ai-agent/skills/` — no local copies needed.

| Skill | Trigger phrases |
| --- | --- |
| `rag/data-hub-promote` | "promote to data hub", "ingest this journal", "add to the archive" |
| `rag/lancedb-search` | "search the journal archive", "find articles on", "RAG search", "what issues cover" |
| `scraping/bright-data-mcp` | "fetch this URL", "look up online", any live web lookup |
| `scraping/search` | "search for", "find genealogy sources on", SERP discovery |
| `memory/prior-context-check` | "what do I know about", "check prior context", "have I seen this" |

## Gotchas

- **BJH must be mounted** for `make sync-lacie` and `make index-raw`
- **Python 3.12 required** — matches all other data-hub repos
- `make sync-data-hub` pulls from `~/Laboratory/data-hub/genealogy/` and
  `~/Laboratory/data-hub/american-history/` only — never pulls private content
