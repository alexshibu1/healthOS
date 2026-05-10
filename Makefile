# Public demo pipeline — uses committed ``data/examples/alex_demo`` fixtures.
# Regenerate CSV slice from local ``rawdata/`` (developer machine only):
#   python scripts/build_alex_demo_dataset.py --end-date 2026-04-30 --days 60

ROOT := $(CURDIR)
DEMO := $(ROOT)/data/examples/alex_demo
SINCE := 2026-03-01
UNTIL := 2026-04-30
MONTH := 2026-04

.PHONY: demo demo-pipeline demo-web demo-build demo-dataset dev api-dev web-dev

demo-dataset:
	python scripts/build_alex_demo_dataset.py --end-date $(UNTIL) --days 60

# Local app: FastAPI (8787) + Vite (5173). Press Ctrl+C to stop both when using -j2.
dev:
	$(MAKE) -j2 api-dev web-dev

api-dev:
	PYTHONPATH=$(ROOT) uvicorn src.api.app:app --host 127.0.0.1 --port 8787 --reload

web-dev:
	cd $(ROOT)/web && npm run dev

demo-pipeline:
	RAWDATA_ROOT=$(DEMO) CONTEXT_FLAGS=$(DEMO)/context_flags.yaml HEALTHOS_PROFILE=$(DEMO)/profile.yaml \
		python -m src.ingest.load_all --since $(SINCE)
	RAWDATA_ROOT=$(DEMO) CONTEXT_FLAGS=$(DEMO)/context_flags.yaml HEALTHOS_PROFILE=$(DEMO)/profile.yaml \
		python -m src.score.nlr_hrv_readiness --since $(SINCE) --until $(UNTIL)
	RAWDATA_ROOT=$(DEMO) CONTEXT_FLAGS=$(DEMO)/context_flags.yaml HEALTHOS_PROFILE=$(DEMO)/profile.yaml \
		python -m src.score.sri --since $(SINCE) --until $(UNTIL)
	RAWDATA_ROOT=$(DEMO) CONTEXT_FLAGS=$(DEMO)/context_flags.yaml HEALTHOS_PROFILE=$(DEMO)/profile.yaml \
		python -m src.score.aerobic_decoupling --since $(SINCE) --until $(UNTIL)
	CONTEXT_FLAGS=$(DEMO)/context_flags.yaml HEALTHOS_PROFILE=$(DEMO)/profile.yaml \
		python -m src.score.composite --since $(SINCE) --until $(UNTIL)
	HEALTHOS_PROFILE=$(DEMO)/profile.yaml \
		python -m src.score.bio_age --daily-csv $(DEMO)/systemic_daily.csv --chronological-age 24
	python -m src.trends --month $(MONTH) --csv $(DEMO)/systemic_daily.csv
	HEALTHOS_PROFILE=$(DEMO)/profile.yaml CONTEXT_FLAGS=$(DEMO)/context_flags.yaml \
		python -m src.interventions --date $(UNTIL)
	CONTEXT_FLAGS=$(DEMO)/context_flags.yaml HEALTHOS_PROFILE=$(DEMO)/profile.yaml \
		python -m src.report.snapshot_builder --date $(UNTIL) --out $(ROOT)/web/src/data/snapshot.json

demo-web:
	cd $(ROOT)/web && npm install && npm run build && npm run dev

demo-build: demo-pipeline
	cd $(ROOT)/web && npm install && npm run build

# Runs demo-pipeline then demo-web. npm run dev keeps the dev server running;
# press Ctrl+C in the terminal to exit.
demo: demo-pipeline demo-web
