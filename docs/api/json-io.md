# JSON-Importe (`shared.json_io`)

Sicheres Laden von JSON-Daten aus nicht vertrauenswürdigen Quellen (z. B. ChatGPT-Antworten).

## Funktionen

### `safe_json_loads`

```python
def safe_json_loads(
    data: str,
    max_size: int = 10_000_000,
) -> Any:
```

Lädt JSON aus einem String mit Sicherheitsprüfungen:

- **Größenbegrenzung**: Maximal `max_size` Bytes (Default 10 MB)
- **Fence-Stripping**: Entfernt UTF-8 BOM und Markdown-Codefence-Artifakte (z. B. ```json)
- **Audit**: Erzeugt Audit-Event `json.load`

**Wirft:** `ValueError` bei Überschreitung des Größenlimits, `json.JSONDecodeError` bei ungültigem JSON

### `require_object`

```python
def require_object(value: Any) -> dict:
```

Stellt sicher, dass ein Wert ein `dict` ist. Wirft `TypeError` sonst.

### `require_array`

```python
def require_array(value: Any) -> list:
```

Stellt sicher, dass ein Wert eine `list` ist. Wirft `TypeError` sonst.

## Verwendung

```python
from shared.json_io import safe_json_loads, require_object

data = safe_json_loads(chunk)
obj = require_object(data)  # garantiert dict
```

## Umgestellte Module

- `risikobewertung/prompts.py`
- `compliance/gui_module.py`
- `gutachten/gui_module.py`
- `vcs/issue_assistant.py`
