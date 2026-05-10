#!/bin/bash
echo 'source /workspace/.venv/bin/activate' >> ~/.bashrc
uv run -- python -c 'print(\"uv environment ready\")'
