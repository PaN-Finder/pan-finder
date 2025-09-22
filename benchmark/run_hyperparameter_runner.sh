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

expand_to_absolute_path() {
  # Take the input path as the first argument
  local input_path="$1"

  # If the path starts with "~", replace it with the value of $HOME
  if [[ "$input_path" == ~* ]]; then
    input_path="${HOME}${input_path:1}" # Replace "~" with $HOME
  fi

  # If the path is already absolute, return it as is
  if [[ "$input_path" == /* ]]; then
    echo "$input_path"
  else
    # Convert relative paths to absolute using cwd (current working directory)
    echo "$(cd "$(dirname "$input_path")" && pwd)/$(basename "$input_path")"
  fi
}


BENCHMARK_RUN="src/hyperparameter_runner.py"
echo "BENCHMARK_RUN ${BENCHMARK_RUN}"
BENCHMARKS_FOLDER="hyperparameters"
echo "BENCHMARKS_FOLDER ${BENCHMARKS_FOLDER}"

for file in "${BENCHMARKS_FOLDER}"/*.json
do
  fullpath_file=$(realpath "${file}")
  echo "Running benchmark from file ${fullpath_file}"
  echo ""
  cmd="python ${BENCHMARK_RUN} -p ${fullpath_file}"
  echo "Python command: ${cmd}"
  echo ""
  echo "---------------------------------------------"
  python ${BENCHMARK_RUN} -p "${fullpath_file}"
  echo "---------------------------------------------"
done

