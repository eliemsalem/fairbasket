#!/usr/bin/env bash
# Réinstalle les extensions VS Code de l'ordinateur d'origine.
# Supprime les lignes des extensions dont tu n'as pas besoin.
set -u

if ! command -v code >/dev/null 2>&1; then
  echo "La commande 'code' est introuvable. Installe VS Code d'abord (voir RECUPERATION_VSCODE.md)."
  exit 1
fi

EXTENSIONS=(
  anthropic.claude-code
  ms-python.python
  ms-python.vscode-pylance
  ms-python.debugpy
  ms-python.vscode-python-envs
  ms-python.black-formatter
  ms-python.flake8
  mechatroner.rainbow-csv
  tomoki1207.pdf
  eamodio.gitlens
  github.vscode-pull-request-github
  ms-ceintl.vscode-language-pack-fr
  batisteo.vscode-django
  openai.chatgpt
  openai.codex-audio
  silasnevstad.gpthelper
)

for ext in "${EXTENSIONS[@]}"; do
  echo "→ $ext"
  code --install-extension "$ext" --force || echo "  échec pour $ext"
done

echo "Terminé. Redémarre VS Code."
