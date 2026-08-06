PY ?= python3
VENV := .venv
BIN := $(VENV)/bin
PORT ?= 8484
HOST ?= 0.0.0.0

.PHONY: help venv install run dev test adduser users status models scan-library reprocess clean

help:
	@echo "make install       create the venv and install dependencies"
	@echo "make adduser       create an account (prints the iOS Shortcut token)"
	@echo "make run           serve on http://localhost:$(PORT)"
	@echo "make dev           same, with auto-reload"
	@echo "make test          run the test suite"
	@echo "make status        queue, model and OCR status"
	@echo "make models        pull the small local models with Ollama"
	@echo "make scan-library  adopt files copied into the library by hand"
	@echo "make reprocess     re-run the AI naming over everything (ARGS=--failed)"

$(BIN)/python:
	$(PY) -m venv $(VENV)

venv: $(BIN)/python

install: venv
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt

run: venv
	$(BIN)/uvicorn app.main:app --host $(HOST) --port $(PORT)

dev: venv
	$(BIN)/uvicorn app.main:app --host $(HOST) --port $(PORT) --reload

test: venv
	$(BIN)/python -m pytest tests -q

adduser: venv
	$(BIN)/python -m app.cli adduser $(NAME)

users: venv
	$(BIN)/python -m app.cli users

status: venv
	$(BIN)/python -m app.cli status

scan-library: venv
	$(BIN)/python -m app.cli scan-library

reprocess: venv
	$(BIN)/python -m app.cli reprocess $(ARGS)

models:
	ollama pull qwen2.5:3b
	@echo "optional vision model for photos OCR can't read:"
	@echo "  ollama pull qwen2.5vl:3b   (then set DOCBOX_VISION_MODEL=qwen2.5vl:3b)"

clean:
	rm -rf $(VENV) .pytest_cache **/__pycache__
