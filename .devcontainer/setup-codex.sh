#!/usr/bin/env bash
# .devcontainer/setup-codex.sh
set -euo pipefail
mkdir -p ~/.codex
cp .codex/config.toml ~/.codex/config.toml
cp .codex/models.json ~/.codex/models.json
# 全局指令、审批规则、自定义技能（按需）
[ -f AGENTS.md ] && cp AGENTS.md ~/.codex/AGENTS.md
[ -d .codex/rules ] && cp -r .codex/rules ~/.codex/rules
# auth.json 刻意不复制：凭据走环境变量或 codex login