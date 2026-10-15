#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================================="
echo "      🎬 Starting AuraVideo - AI Video Generator         "
echo "=========================================================="

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Starting server on http://localhost:8050..."
python3 -m uvicorn server:app --host 0.0.0.0 --port 8050 --reload
