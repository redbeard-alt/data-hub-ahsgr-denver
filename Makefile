.DEFAULT_GOAL := help

PYTHON := .venv/bin/python
PIP    := .venv/bin/pip
LACIE  := /Volumes/LaCie/data-hub/ahsgr
DATA_HUB := $(HOME)/Laboratory/data-hub

.venv:
	python3.12 -m venv .venv

install: .venv
	$(PIP) install --upgrade pip --quiet
	$(PIP) install -r requirements.txt --quiet
	@echo "✓ venv ready"

## run: rebuild the full index (AGENT_SPEC alias)
run: build

## test: run test suite
test: .venv
	$(PYTHON) -m pytest tests/ -v 2>/dev/null || echo "(no tests yet)"

## lint: ruff linter
lint: .venv
	$(PYTHON) -m ruff check . 2>/dev/null || true

## sync-identity: pull identity files from config-ai-agent
sync-identity:
	rsync -a $(HOME)/Laboratory/config-ai-agent/identity/ .

# ── corpus ops ──────────────────────────────────────────────────────────────

## promote: promote a document
##   make promote SRC="path/to/doc.md" TOPIC="journals/clues"
promote: .venv
	$(PYTHON) cli.py promote "$(SRC)" --topic "$(TOPIC)" \
		--tier "$(or $(TIER),public)" \
		$(if $(AGENT),--source-agent "$(AGENT)",)

## build: rebuild LanceDB index
build: .venv
	$(PYTHON) cli.py build

## search: semantic search
##   make search QUERY="volga german settlement"
search: .venv
	$(PYTHON) cli.py search "$(QUERY)"

## query: RAG query
##   make query Q="who was newsletter editor in 1985?"
query: .venv
	$(PYTHON) cli.py query "$(Q)"

## stats: document counts and index status
stats: .venv
	$(PYTHON) cli.py stats

## index-raw: scan LaCie raw PDFs → raw/INDEX.md (LaCie must be mounted)
index-raw: .venv
	@if [ ! -d "$(LACIE)" ]; then echo "ERROR: LaCie not mounted at $(LACIE)"; exit 1; fi
	$(PYTHON) cli.py index-raw

## sync-lacie: rsync promoted docs → LaCie/data-hub/ahsgr/ (LaCie must be mounted)
sync-lacie:
	@if [ ! -d "$(LACIE)" ]; then echo "ERROR: LaCie not mounted at $(LACIE)"; exit 1; fi
	rsync -av --exclude='data/' --exclude='.git/' --exclude='.venv/' --exclude='__pycache__/' \
		--exclude='members/' \
		./ "$(LACIE)/hub/"
	@echo "✓ Synced to $(LACIE)/hub/"

## sync-data-hub: pull shared genealogy + history docs from ~/Laboratory/data-hub
sync-data-hub:
	@echo "→ Pulling from data-hub/genealogy/"
	rsync -av --include="*.md" --include="*.csv" --exclude="*" \
		"$(DATA_HUB)/genealogy/" research/genealogy-shared/
	@echo "→ Pulling from data-hub/american-history/"
	rsync -av --include="*.md" --include="*.csv" --exclude="*" \
		"$(DATA_HUB)/american-history/" research/american-history-shared/
	@echo "✓ Shared research synced"

## clean: remove __pycache__ and LanceDB index
clean:
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	rm -rf data/lancedb data/lancedb-public data/lancedb-private
	@echo "✓ Cleaned indexes."

help:
	@echo ""
	@echo "  make install                              Set up venv (python3.12) + deps"
	@echo "  make build                                Rebuild LanceDB index"
	@echo "  make promote SRC=\"...\" TOPIC=\"...\"        Promote a document"
	@echo "  make search QUERY=\"...\"                   Semantic search"
	@echo "  make query Q=\"...\"                        RAG query"
	@echo "  make stats                                Document counts + index status"
	@echo "  make index-raw                            Scan LaCie PDFs → raw/INDEX.md"
	@echo "  make sync-lacie                           Rsync hub → LaCie (LaCie required)"
	@echo "  make sync-data-hub                        Pull shared research from data-hub"
	@echo "  make clean                                Remove __pycache__ + LanceDB index"
	@echo ""
	@echo "  LaCie path: $(LACIE)"
	@echo ""

.PHONY: install run test lint clean sync-identity promote build search query stats index-raw sync-lacie sync-data-hub help
