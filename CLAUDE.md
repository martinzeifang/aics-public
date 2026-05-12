# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI Compliance Suite** is a multi-module Python application for managing compliance questionnaires and reports. It provides GUI-based and CLI workflows for:

- Ingesting existing compliance responses (XLSX/DOCX) into SQLite
- Generating prompts for new questionnaires by finding similar examples
- Applying ChatGPT responses back to output documents

**Key principle**: Semi-automated workflow where prompts are pasted into ChatGPT, responses are saved as JSON, then applied back to documents. This avoids direct API calls to ChatGPT Pro which lacks official support.

## Module Architecture

The suite consists of 11 independent modules, each with consistent structure:

- **BASO**: BASO/ForumISM questionnaires
- **ICT**: ICT security questionnaires  
- **Compliance**: Compliance reports and assessments
- **CRA**: Compliance Risk Assessment (OWASP Proactive Controls)
- **DSGVO**: GDPR compliance
- **NIS2**: NIS2 directive compliance
- **AI Act**: EU AI Act compliance
- **Gutachten**: Expert opinions/reports
- **Compliance-DB**: Database-driven compliance with Ollama integration
- **Kunden**: Customer management
- **Risikobewertung**: Risk assessments

### Shared Components

- **shared/**: Common utilities (`db_viewer.py`, `issue_sync.py`, issue linking)
- **vcs/**: GitHub/GitLab issue integration (`github_issues.py`, `gitlab_issues.py`, `issue_assistant.py`)
- **ai_compliance_suite/**: Main suite GUI + authentication system

## Module Structure

Each module follows this pattern:

```
<module>/
├── __main__.py          # Entry point: from .cli import main
├── cli.py              # CLI subcommands (ingest, prepare, apply, gui)
├── gui_module.py       # *ModuleFrame class for suite integration
├── gui.py              # Standalone GUI launcher
├── config.py           # Config loading/saving with defaults
├── db.py               # SQLite database operations
├── io_xlsx.py          # Excel reading/writing
├── io_docx.py          # Word document handling (if applicable)
└── <domain>.py         # Domain-specific logic (prompts, answers, etc.)

<module>.config.json    # User-editable configuration (created on first run)
```

### Standard CLI Workflow

Each module implements these subcommands:

1. **ingest** - Parse existing documents, extract data, store in SQLite
   - Example: `python -m baso ingest --source data/baso/quelle --db data/db/baso.sqlite`
   - For BASO also: `python -m baso ingest-sikos --sikos data/shared/sikos --db data/db/baso.sqlite`

2. **prepare** - Generate prompts for new documents, using similar examples from DB
   - Example: `python -m baso prepare --new data/baso/neu --db data/db/baso.sqlite --out out/baso/prompts`
   - Creates empty JSON templates in answers directory

3. **apply** - Write ChatGPT JSON responses back to output documents
   - Example: `python -m baso apply --new data/baso/neu --answers out/baso/answers --out out/baso/filled`

4. **gui** - Launch standalone module GUI

### GUI Integration

The suite GUI (`ai_compliance_suite.gui:run_suite_gui()`) integrates modules via:

```python
from <module>.gui_module import <Module>ModuleFrame
```

Each `*ModuleFrame` inherits `ttk.Frame` and implements the same interface. The suite adds tabs for each module dynamically. UI config is shared across modules and stored in `ai_compliance_suite.config.json`.

**Important**: GUI module fonts/colors follow a consistent scheme:
- Header backgrounds: `#1565c0` (blue)
- Accent text: `#90caf9` (light blue)
- Fonts: "Segoe UI" for labels, "Consolas" for code/JSON
- Padding: typically `padx=24, pady=16` for headers

## Command Reference

### Development & Testing

```bash
# Setup
pip install -r requirements.txt
# Linux Tkinter (required for GUI)
sudo apt install python3-tk    # Debian/Ubuntu
sudo dnf install python3-tkinter  # Fedora
sudo pacman -S tk              # Arch

# Run main GUI suite
python -m ai_compliance_suite
# or: ./start-suite.sh

# Run individual module CLI
python -m baso ingest --source data/baso/quelle --db data/db/baso.sqlite
python -m baso prepare --new data/baso/neu --db data/db/baso.sqlite --out out/baso/prompts
python -m baso apply --new data/baso/neu --answers out/baso/answers --out out/baso/filled
python -m baso gui

# Run other modules (ict, compliance, cra, dsgvo, etc.)
python -m ict ingest --source data/ict/quelle --db data/db/ict.sqlite
python -m compliance gui

# Database utilities
python -m shared.db_viewer data/db/baso.sqlite
```

### Desktop Integration (Linux)

```bash
./install-desktop-entry.sh  # Makes "AI Compliance Suite" available in app menus
```

## Data Flow & Directory Structure

```
data/
├── baso/
│   ├── quelle/          # Existing BASO questionnaires (XLSX)
│   └── neu/             # New BASO questionnaires to process (XLSX)
├── ict/
│   ├── quelle/          # Existing ICT questionnaires (XLSX)
│   └── neu/             # New ICT questionnaires
├── compliance/berichte/ # Compliance reports (DOCX)
├── shared/sikos/        # Security concepts (DOCX, shared across modules)
└── db/                  # SQLite databases (created by ingest)
    ├── baso.sqlite
    ├── ict.sqlite
    └── <module>.sqlite

out/
├── baso/
│   ├── prompts/         # Generated prompts (markdown files)
│   ├── answers/         # JSON responses (manual copy from ChatGPT)
│   └── filled/          # Final XLSX with ChatGPT answers applied
├── ict/
│   └── (same structure)
└── <module>/
    └── (same structure)
```

## Configuration System

Each module uses a `.config.json` file (e.g., `baso.config.json`):

- **Auto-created** on first run with sensible defaults
- **User-editable** without code changes (UTF-8 encoding)
- **GUI edit dialog** in each module under "Bearbeiten" (Edit) menu

Key config sections:
- **paths**: Data directories, DB paths, output folders
- **ui**: GUI options (batch size, similarity top-k, debug mode, etc.)
- **bericht/report**: Document metadata (organization name, version, confidentiality)
- **gitlab** (if applicable): Base URL, token environment variable

The suite config (`ai_compliance_suite.config.json`) also supports **authentication** (via `auth.is_auth_enabled()` and `show_login_dialog()`).

## Special Notes

### ChatGPT Integration

This is **not** an API-based automation. The workflow requires:

1. Copy generated prompt to ChatGPT
2. Paste ChatGPT response as structured JSON back into the tool
3. Apply responses to output documents

This design respects ChatGPT Pro's lack of official API while avoiding legal/ToS issues.

### Prompt Generation Strategy

The `prepare` command uses **similarity matching**:
- Queries existing answers from SQLite for similar questions
- Returns top-k examples to provide context in prompts
- Configurable via `--top` and `--batch-size` flags
- Uses `rapidfuzz` for fuzzy string matching (see `requirements.txt`)

### Excel/Word Layouts

- **BASO**: Recognizes two layouts: "System" questionnaires (from `quelle/`) and "Service" attachments (from `neu/`)
- **Service layout**: No separate "security goals" column; mapped to remarks
- **Logo rendering**: Tries to render `File-22.svg` via Inkscape/ImageMagick; falls back to Canvas icon

### Compliance-DB Module (Ollama)

Only used by `compliance_db` module. Install separately:

```bash
# Windows
./install-ollama.bat

# Linux  
chmod +x install-ollama.sh
./install-ollama.sh
```

## Code Patterns

### Module Config Loading

```python
from <module>.config import load_config, save_config, DEFAULT_CONFIG_PATH

cfg = load_config(Path("<module>.config.json"))
cfg["ui"]["batch_size"] = 20
save_config(cfg, Path("<module>.config.json"))
```

### Database Access

```python
from <module>.db import ensure_db

db_path = Path("data/db/baso.sqlite")
ensure_db(db_path)  # Creates tables if needed
# Then use sqlite3: conn = sqlite3.connect(db_path)
```

### Excel I/O

```python
from <module>.io_xlsx import read_questionnaire, write_filled

wb = read_questionnaire(excel_path)
# Process...
write_filled(wb, output_path, evaluated_by="ChatGPT")
```

### GUI Module Registration

When adding a new module's GUI to the suite, add to `ai_compliance_suite/gui.py`:

```python
from <module>.gui_module import <Module>ModuleFrame
# ...
notebook.add(
    <Module>ModuleFrame(notebook, bg=bg_color),
    text="<Display Name>"
)
```

## GitHub Project & Issue Sync

### In-App Issue Integration

The `vcs/` module provides GitHub/GitLab integration:

- `issue_assistant.py`: Interactive dialog to draft issues (Tkinter)
- `github_issues.py`, `gitlab_issues.py`: Create issues via API
- `issue_sync.py`: Sync issues to project board

The issue assistant uses Claude (via prompt) to convert user input → structured issue JSON.

### Project Workflow

**GitHub Project 2**: [github.com/users/martinzeifang/projects/2](https://github.com/users/martinzeifang/projects/2)

**Issue-First Workflow**:

1. Create GitHub issue using the **Module Task** template:
   - Select module (BASO, ICT, CRA, etc.)
   - Set priority (P0–P3)
   - Define acceptance criteria
   - Link affected areas (GUI, CLI, DB, etc.)

2. Create feature branch named after issue:
   ```bash
   git checkout -b module/description-#123
   ```

3. Work on feature, commit with reference:
   ```bash
   git commit -m "feat(module): description

   - Specific change
   - Another change
   
   Closes #123"
   ```

4. When PR merges, issue auto-closes via GitHub link

**Weekly Sync**: GitHub Actions runs every Monday at 9 AM UTC, summarizing:
- All open issues by module/priority
- Recent commits on active branches
- Project status report (view in Actions tab)

**Manual Sync Checklist** (if auto-sync not active):
- [ ] Review GitHub Project #2 columns (Planned/In Progress/Done)
- [ ] Verify open issues match active branches
- [ ] Update issue status labels as work progresses
- [ ] Check for stale branches without corresponding issues

## Testing

No automated test suite currently defined. Manual workflows:

1. Test `ingest` on sample questionnaires
2. Verify `prepare` generates well-formed prompts
3. Manually paste a prompt into ChatGPT, save JSON response
4. Test `apply` writes answers correctly to output XLSX
5. Verify GUI loads all module tabs without errors

## Dependencies

Key packages (see `requirements.txt`):

- `openpyxl>=3.1.5` - Excel handling
- `python-docx>=1.2.0` - Word document handling
- `rapidfuzz>=3.14.0` - Fuzzy similarity for prompt context
- `pillow>=10.0.0` - Image processing (for logo rendering)
- `pdfplumber>=0.11.0` - PDF text extraction
- `requests>=2.32.0` - HTTP requests (GitHub/GitLab API)

## Common Development Tasks

### Adding a New Module

1. Create `<newmodule>/` directory
2. Implement required files: `__main__.py`, `cli.py`, `gui_module.py`, `config.py`, `db.py`
3. Define CLI subcommands in `cli.py` (ingest, prepare, apply, gui)
4. Create `<newmodule>ModuleFrame(ttk.Frame)` in `gui_module.py`
5. Add to suite GUI: import and add tab in `ai_compliance_suite/gui.py`
6. Create `<newmodule>.config.json` template in module's `config.py:default_config()`

### Modifying GUI Styling

- Header colors: Edit `gui_module.py` frame background (`bg="#1565c0"`)
- Font sizes: Standardized at module level (usually "Segoe UI", 9–18pt)
- Padding: Use 24px horizontal, 16px vertical for headers/containers
- Keep consistent with existing modules for visual cohesion

### Working with SQLite

- Use `sqlite3` module (stdlib)
- Define schema in `<module>/db.py:ensure_db()`
- No ORM; direct SQL queries for simplicity
- Use `Path.absolute()` for cross-platform path handling

### Git Workflow

- Branch naming: `<module>/<feature>` (e.g., `cra/ai-main`)
- Commits: Descriptive message, reference module(s) affected
- Keep GitHub Project #2 synchronized: update issue status as work progresses
