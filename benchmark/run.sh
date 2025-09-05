#!/bin/bash

if [ ! -f ".env" ]; then
    echo ".env file not found!"
    exit 1
fi

# load envirionment variables from .env file
set -o allexport
source .env
set -o allexport

# create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    python -m venv .venv

    pip install --upgrade pip
    pip install -r requirements.txt
fi

# activate virtual environment
source .venv/bin/activate

# run the benchmark script
python src/main.py

