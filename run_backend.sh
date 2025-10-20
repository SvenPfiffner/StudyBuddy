#!/usr/bin/env bash
# Run the StudyBuddy backend with optional host and port arguments.

# Default values
HOST="0.0.0.0"
PORT="8000"

# Parse command-line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --host) HOST="$2"; shift ;;
        --port) PORT="$2"; shift ;;
        *) echo "Unknown parameter: $1" >&2; exit 1 ;;
    esac
    shift
done

# Resolve script directory to handle relative paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Path to virtual environment's Python
VENV_PY="$SCRIPT_DIR/backend/.venv/bin/python"

# Check if the virtual environment exists
if [ ! -x "$VENV_PY" ]; then
    echo "Error: Python virtual environment not found at:"
    echo "  $VENV_PY"
    echo "Please ensure the backend venv is created and installed."
    exit 1
fi

# Run the FastAPI app
echo "Starting StudyBuddy backend on host ${HOST}, port ${PORT}..."
"$VENV_PY" -m uvicorn backend.main:app --host "$HOST" --port "$PORT"
