#!/usr/bin/env bash
# Run the StudyBuddy frontend development server.

# Resolve script directory to handle relative paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Path to frontend directory
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Check if the frontend directory exists
if [ ! -d "$FRONTEND_DIR" ]; then
    echo "Error: Frontend directory not found at:"
    echo "  $FRONTEND_DIR"
    exit 1
fi

# Check if npm is installed
if ! command -v npm >/dev/null 2>&1; then
    echo "Error: npm is not installed or not in PATH."
    echo "Please install Node.js (https://nodejs.org/) before running this script."
    exit 1
fi

# Move into frontend directory
cd "$FRONTEND_DIR" || exit 1

# Install dependencies if node_modules is missing
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Run the frontend dev server
echo "Starting StudyBuddy frontend..."
npm run dev
