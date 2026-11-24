"""Cross-Module Word-Vorlagen-Engine (#988).

Zentrale, von der Admin-UI verwaltete Template-Engine für mehrere Compliance-
Module (CRA, NIS2, AI Act, DSGVO, Risikobewertung). Unabhängig vom Gutachten-
Renderer. DOCX-Rendering via docxtpl, optional PDF via LibreOffice headless.
"""
from __future__ import annotations

DEFAULT_DB_PATH = "data/db/templates.sqlite"
SUPPORTED_MODULES = ("cra", "nis2", "aiact", "dsgvo", "risikobewertung")
