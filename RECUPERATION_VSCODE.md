# Récupérer le projet APP COURSE et Visual Studio Code sur un autre ordinateur

Écrit le 26/10/2026 depuis l'ordinateur d'origine (Ubuntu 24.04, VS Code 1.142.0, Python 3.12).

## 1. Ce que contient le dossier

| Élément | Rôle |
|---|---|
| `Carrefour/`, `Monoprix/`, `Naturalia/` | Tickets de caisse en PDF (mars 2024 à octobre 2026) |
| `Appareil photo/` | Photos de tickets papier |
| `poc/parse_receipts.py` | Lit les PDF et écrit `poc/data/receipts.csv` et `items.csv` |
| `poc/add_photo_receipts.py` | Ajoute les tickets pris en photo |
| `poc/analyze.py` | Calcule les indicateurs, écrit `poc/data/kpis_summary.txt` |
| `poc/report.html` | Rapport « Vos 5 courses du quotidien » (s'ouvre dans un navigateur) |
| `RECUPERATION_VSCODE.md` | Ce document |
| `installer_extensions_vscode.sh` | Réinstalle les extensions VS Code d'un coup |

Les tickets contiennent tes habitudes d'achat : ne pose pas le dossier dans un dépôt public et ne l'envoie pas sur un service que tu ne maîtrises pas.

## 2. Copier le dossier

Décompresser `APP COURSE.zip` dans le dossier `Documents` de l'autre ordinateur. Le chemin attendu est `~/Documents/APP COURSE`. Les scripts utilisent des chemins relatifs, donc un autre emplacement fonctionne aussi.

```bash
cd ~/Documents
unzip "APP COURSE.zip"
```

## 3. Installer Visual Studio Code

**Ubuntu / Debian**
```bash
sudo snap install code --classic
```
Ou télécharger le paquet `.deb` sur https://code.visualstudio.com/ puis `sudo apt install ./code_*.deb`.

**Windows / Mac** : installeur sur https://code.visualstudio.com/.

Vérifier que la commande `code` existe :
```bash
code --version
```
Sous Mac, ouvrir VS Code, `Cmd+Maj+P`, puis « Shell Command: Install 'code' command in PATH ».

## 4. Réinstaller les extensions

Depuis le dossier du projet :
```bash
bash installer_extensions_vscode.sh
```
Le script installe les 16 extensions de l'ordinateur d'origine. Retire de la liste celles que tu n'utilises pas.

| Extension | Utilité |
|---|---|
| `anthropic.claude-code` | Claude Code dans VS Code |
| `ms-python.python`, `ms-python.vscode-pylance`, `ms-python.debugpy`, `ms-python.vscode-python-envs` | Python |
| `ms-python.black-formatter`, `ms-python.flake8` | Mise en forme et vérification du code |
| `mechatroner.rainbow-csv` | Lire les CSV du POC |
| `tomoki1207.pdf` | Voir les tickets PDF dans VS Code |
| `eamodio.gitlens`, `github.vscode-pull-request-github` | Git et GitHub |
| `ms-ceintl.vscode-language-pack-fr` | Interface en français |
| `batisteo.vscode-django` | Django (pas utile pour ce projet) |
| `openai.chatgpt`, `openai.codex-audio`, `silasnevstad.gpthelper` | Outils OpenAI |

## 5. Réglages

Contenu de `settings.json` sur l'ordinateur d'origine :
```json
{
    "python.defaultInterpreterPath": "/bin/python3",
    "claudeCode.hideOnboarding": true
}
```
Un réglage de l'ancien fichier (`tabnine.experimentalAutoImports`) concerne une extension qui n'est plus installée : ne le recopie pas. Pour `python.defaultInterpreterPath`, laisse VS Code détecter Python tout seul, ou choisis-le avec `Ctrl+Maj+P` puis « Python: Select Interpreter ». Sous Windows, le chemin sera différent.

Je n'ai pas copié `mcp.json` ni les profils : ils peuvent contenir des clés ou des identifiants. Recrée-les à la main si besoin.

**Autre méthode** : dans VS Code, `Ctrl+Maj+P` puis « Settings Sync: Turn On » avec ton compte GitHub ou Microsoft. Les réglages et les extensions suivent les deux ordinateurs. À activer seulement si tu es d'accord pour qu'ils passent par ces services.

## 6. Faire marcher le POC

Il faut Python 3.10 ou plus, `pandas` et `pdftotext` (qui fait partie de poppler).

```bash
# Ubuntu / Debian
sudo apt install python3 python3-pip python3-venv poppler-utils

cd ~/Documents/"APP COURSE"
python3 -m venv .venv
source .venv/bin/activate
pip install pandas

cd poc
python3 parse_receipts.py
python3 add_photo_receipts.py
python3 analyze.py
```

Sous Mac : `brew install poppler`. Sous Windows : installer poppler, ajouter son dossier `bin` au PATH, puis lancer les mêmes commandes dans PowerShell.

Résultat attendu (données du 26/10/2026) : 95 tickets, 3 227,17 € de dépenses totales, panier moyen 33,97 €. Si les chiffres sont différents, un ticket n'a pas été lu : relance `parse_receipts.py` et regarde les messages d'erreur.

Si `add_photo_receipts.py` demande un module ou un outil en plus, lis les premières lignes du fichier : l'import ou le commentaire en tête le dit.

## 7. Ouvrir le projet dans VS Code

```bash
cd ~/Documents/"APP COURSE"
code .
```
Pour reprendre avec Claude Code : ouvrir le terminal de VS Code, lancer `claude`, et ouvrir le questionnaire de l'application sur claude.ai (il est lié à ton compte, donc disponible sur l'autre ordinateur). La liste « Questionnaire App Courses » se retrouve dans tes artifacts, et tes réponses sont enregistrées avec.
