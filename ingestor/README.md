# Pand-Finder Ingestor

It is an initial collection of scripts to ingest data into the Pan-Finder database.
The ingestor service can be implemented based on this source code.

## Install requirements

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Create a `.env` file from `.env.example` and fill in the required variables.

## Run the ingestor

```bash
./run.sh
```
