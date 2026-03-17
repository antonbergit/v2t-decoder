.PHONY: install test run

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r requirements-dev.txt

test:
	. .venv/bin/activate && pytest -q

run:
	. .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000
