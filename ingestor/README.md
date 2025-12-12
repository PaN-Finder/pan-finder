# Pan‑Finder Ingestor

This folder contains an initial set of scripts for ingesting data into the Pan‑Finder database.
A production‑grade ingestor service can be implemented based on this source code.

## Install dependencies

- Python 3.12+
- Source of truth: `pyproject.toml` (runtime deps + dev extras). Pinned installs are generated `requirements*.txt`.
- Create a venv and install pinned deps:
	```bash
	python -m venv .venv
	source .venv/bin/activate
	pip install -r requirements.txt
	```
- Server code is imported by the benchmark. Install server dependencies:
	```bash
	cd ../server
	python -m venv .venv
	source .venv/bin/activate
	pip install -r requirements.txt
	```
    
## Configuration

Create a `.env` file from `.env.example` and set the required variables.

## Database setup

You can find SQL scripts to set up the database schema in the `database` folder.

## Prepare data

You can find data in the [deliverables](https://github.com/PaN-Finder/deliverables/tree/main/task-1/data) repository.
Downloadt theme into the `data` folder.

## Run the ingestor

```bash
./run.sh
```
