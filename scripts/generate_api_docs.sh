#!/bin/bash
# Generate API documentation using pdoc
set -e
pip install pdoc3 2>/dev/null || pip install pdoc 2>/dev/null
python -m pdoc --html --output-dir docs/api bridges config protocols exceptions
echo "API docs generated in docs/api/"
