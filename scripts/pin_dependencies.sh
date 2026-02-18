#!/bin/bash
# Pin all dependencies to exact versions
pip install pip-tools
pip-compile requirements.txt --output-file requirements-pinned.txt
echo "Pinned requirements saved to requirements-pinned.txt"
