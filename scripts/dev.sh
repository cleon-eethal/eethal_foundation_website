#!/bin/bash
#
# Start the EETHAL Foundation dev environment
#
# Runs the Hugo dev server and Tailwind CSS watcher side by side.
# Press Ctrl+C to stop both.
#

set -e

# Ensure we're in the repo root
cd "$(dirname "$0")/.."

echo "Starting EETHAL dev environment..."
echo "  Hugo server:  http://localhost:1313/"
echo "  CSS watcher:  watching assets/css/main.css"
echo ""
echo "Press Ctrl+C to stop."
echo ""

# Start CSS watcher in background
npm run watch:css &
CSS_PID=$!

# Start Hugo dev server in background
hugo server -D &
HUGO_PID=$!

# Clean up both on exit
trap "kill $CSS_PID $HUGO_PID 2>/dev/null; echo ''; echo 'Dev environment stopped.'" EXIT

# Wait for either to exit
wait
