# data-hub-ashgr-denver

Curated document archive for the ASHGR North Denver Chapter. Promotes from research-agent,
newsletter-agent, and project-ashgr-denver into a single LanceDB index for RAG search.

**Raw source:** `/Volumes/LaCie/data-hub/ahsgr/journals/` — 462 PDFs (1971–present), 1.8GB

## Quick Start

```bash
make install
make index-raw      # scan LaCie PDFs → raw/INDEX.md (LaCie required)
make build          # build LanceDB index from promoted docs
make search QUERY="volga german settlement patterns"
make query Q="who was newsletter editor in 1985?"
make stats
```

## Taxonomy

| Path | Content |
|---|---|
| `journals/clues/` | AHSGR CLUES newsletter (genealogy tips, 1973–) |
| `journals/journal/` | Main AHSGR Journal |
| `journals/work-papers/` | Early work papers (1971–1977) |
| `journals/jugendezeitung/` | JugendZeitung (German-language youth publication) |
| `journals/newsletter/` | Chapter/national newsletters |
| `board/roster/` | Officer and board records (from project-ashgr-denver) |
| `board/meetings/` | Meeting notes and agendas |
| `members/` | Member directory — always private, gitignored |
| `genealogy/` | Germans from Russia genealogy research |
| `research/` | Shared docs from data-hub |

## Multi-Agent Promote

```python
import subprocess
from pathlib import Path
subprocess.run([
    str(Path.home() / "Laboratory/data-hub-ashgr-denver/.venv/bin/python"),
    str(Path.home() / "Laboratory/data-hub-ashgr-denver/cli.py"),
    "promote", str(src_path), "--topic", "journals/clues", "--source-agent", "research-agent",
])
```

See `CLAUDE.md` for full architecture and rules.
