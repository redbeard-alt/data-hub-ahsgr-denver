---
name: ingest-journals
description: Extract and promote ASHGR journal PDFs from LaCie into the data-hub-ashgr-denver index
---

# ingest-journals

Batch extract text from AHSGR PDF journals on LaCie and promote to the hub.

## When to use

- Initial corpus ingestion
- New journal issues added to LaCie
- Re-extracting a series after extraction quality issues

## Steps

1. **Check what's on LaCie**
```bash
cd ~/Laboratory/data-hub-ashgr-denver
make index-raw
cat raw/INDEX.md
```

2. **Extract text from PDFs** (requires pdfplumber)
```bash
.venv/bin/python - <<'PY'
import pdfplumber
from pathlib import Path

SERIES = "CLUES"   # change per run: CLUES, Journal, WorkPaper, etc.
SRC = Path("/Volumes/LaCie/data-hub/ahsgr/journals")
OUT = Path("journals/clues")  # adjust per series
OUT.mkdir(exist_ok=True)

for pdf in sorted(SRC.glob(f"*{SERIES}*.pdf")):
    with pdfplumber.open(pdf) as doc:
        text = "\n\n".join(p.extract_text() or "" for p in doc.pages)
    slug = pdf.stem.lower().replace("ahsgr-", "").replace("_", "-")
    out = OUT / f"{slug}.md"
    out.write_text(f"# {pdf.stem}\n\n{text}", encoding="utf-8")
    print(f"  ✓ {out.name}  ({len(text):,} chars)")
PY
```

3. **Promote extracted files**
```bash
for f in journals/clues/*.md; do
  .venv/bin/python cli.py promote "$f" --topic journals/clues --source-agent research-agent
done
```

4. **Rebuild index** — `make build`

## Notes

- LaCie must be mounted: `/Volumes/LaCie/data-hub/ahsgr/journals/`
- Scanned PDFs (pre-1990) may need OCR — use research-agent's OCR pipeline first
- Journal series uses Vol/No numbering, not years — include `--series journal` flag
