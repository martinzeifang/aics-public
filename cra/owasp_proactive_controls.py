"""OWASP Proactive Controls (v3) - checklist metadata with CRA article mapping."""

from __future__ import annotations

from typing import Any


OWASP_PC_V3: list[dict[str, Any]] = [
    {
        "id": "OWASP-PC-C1",
        "title": "Define Security Requirements",
        "description": (
            "Sicherheitsanforderungen müssen explizit als Teil des Entwicklungsprozesses "
            "definiert und dokumentiert werden – z. B. als User Stories, Threat Models oder "
            "Security Checklisten. Ohne formale Anforderungen fehlt die Grundlage für alle "
            "weiteren Sicherheitsmaßnahmen."
        ),
        "cra_articles": ["Anhang I Part I Nr. 1", "Art. 13 Abs. 1", "Art. 13 Abs. 5"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "SECURITY.md, Threat-Model-Dokument, Security-Anforderungsliste, "
            "Risikobewertung (z. B. STRIDE), Security-User-Stories im Backlog."
        ),
    },
    {
        "id": "OWASP-PC-C2",
        "title": "Leverage Security Frameworks and Libraries",
        "description": (
            "Statt Sicherheitsfunktionen selbst zu implementieren, sollen geprüfte und "
            "aktiv gepflegte Bibliotheken (z. B. für Kryptografie, Auth, Validierung) "
            "eingesetzt werden. Eigene Implementierungen sind fehleranfällig und schwer "
            "auditierbar."
        ),
        "cra_articles": ["Anhang I Part I Nr. 2", "Anhang I Part II Nr. 1"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Dependency-Management-Policy, SBOM (Software Bill of Materials), "
            "Liste genutzter Security-Libraries, Renovate/Dependabot-Konfiguration, "
            "Vulnerability-Scan-Report (z. B. Trivy, Snyk)."
        ),
    },
    {
        "id": "OWASP-PC-C3",
        "title": "Secure Database Access",
        "description": (
            "Datenbankzugriffe müssen mit minimalen Rechten (Least Privilege) erfolgen. "
            "SQL-Injection wird durch parametrisierte Abfragen verhindert. Zugangsdaten "
            "dürfen nicht im Quellcode stehen."
        ),
        "cra_articles": ["Anhang I Part I Nr. 4", "Anhang I Part II Nr. 2"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Parametrisierte Queries / ORM-Nutzung im Code, dedizierte DB-User "
            "ohne Admin-Rechte, Secret-Management (Vault, Env-Secrets), "
            "kein Klartext-Passwort im Repository (Secret-Scan-Report)."
        ),
    },
    {
        "id": "OWASP-PC-C4",
        "title": "Encode and Escape Data",
        "description": (
            "Ausgaben an Browser, Shell, XML-Parser etc. müssen kontextabhängig kodiert "
            "werden um XSS, Injection und ähnliche Angriffe zu verhindern. "
            "Templates sollen Auto-Escaping aktiviert haben."
        ),
        "cra_articles": ["Anhang I Part I Nr. 4"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Template-Engine mit aktiviertem Auto-Escape (z. B. Jinja2, React JSX), "
            "Output-Encoding-Richtlinie, SAST-Report (keine XSS-Findings), "
            "Code-Review-Checkliste."
        ),
    },
    {
        "id": "OWASP-PC-C5",
        "title": "Validate All Inputs",
        "description": (
            "Alle Eingaben von außen (Benutzer, APIs, Dateien, Umgebungsvariablen) "
            "müssen vor der Verarbeitung auf Typ, Format und Bereich geprüft werden. "
            "Die Validierung muss serverseitig erfolgen."
        ),
        "cra_articles": ["Anhang I Part I Nr. 4", "Anhang I Part I Nr. 2"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Schema-Validierung (JSON Schema, Pydantic, Zod), serverseitige "
            "Validierungslogik, Fuzzing-Ergebnisse, SAST-Report auf Injection-Findings."
        ),
    },
    {
        "id": "OWASP-PC-C6",
        "title": "Implement Digital Identity",
        "description": (
            "Authentifizierung und Identitätsmanagement müssen sicher implementiert sein: "
            "starke Passwörter/MFA, sichere Session-Verwaltung, keine selbst entwickelten "
            "Auth-Protokolle."
        ),
        "cra_articles": ["Anhang I Part I Nr. 7", "Art. 13 Abs. 3"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "MFA-Konfiguration, Passwort-Policy (NIST 800-63B), Session-Timeout, "
            "OAuth2/OIDC-Integration, FIDO2/WebAuthn-Support, "
            "Auth-Bibliothek (kein Custom-Auth-Code)."
        ),
    },
    {
        "id": "OWASP-PC-C7",
        "title": "Enforce Access Controls",
        "description": (
            "Autorisierungsprüfungen müssen für jede Anfrage serverseitig erfolgen "
            "(Deny-by-Default). Least-Privilege-Prinzip: Nutzer und Dienste haben nur "
            "die minimal notwendigen Rechte."
        ),
        "cra_articles": ["Anhang I Part I Nr. 7", "Anhang I Part II Nr. 2"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Rollenmodell-Dokumentation, RBAC/ABAC-Implementierung, "
            "serverseitige Autorisierungschecks, Pentest-Report (IDOR-Tests), "
            "API-Zugriffsmatrix."
        ),
    },
    {
        "id": "OWASP-PC-C8",
        "title": "Protect Data Everywhere",
        "description": (
            "Daten müssen sowohl in der Übertragung (TLS) als auch im Ruhezustand "
            "(Verschlüsselung) geschützt sein. Schlüsselverwaltung muss sicher sein. "
            "Keine Klartextspeicherung sensibler Daten."
        ),
        "cra_articles": ["Anhang I Part I Nr. 3", "Anhang I Part II Nr. 4"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "TLS-Konfiguration (mind. TLS 1.2), Verschlüsselung at rest "
            "(AES-256 o. ä.), Key-Management-System, Secret-Scan-Report, "
            "Datenschutz-Folgenabschätzung (DSFA)."
        ),
    },
    {
        "id": "OWASP-PC-C9",
        "title": "Implement Security Logging and Monitoring",
        "description": (
            "Sicherheitsrelevante Ereignisse (Logins, Fehler, Zugriffsversuche) müssen "
            "protokolliert werden – ohne sensible Daten in den Logs. Logs müssen "
            "manipulationsgeschützt und auswertbar sein."
        ),
        "cra_articles": ["Art. 13 Abs. 5", "Anhang I Part I Nr. 5"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Logging-Konzept, SIEM-Integration, Security-Event-Definitionen, "
            "kein PII in Logs (Log-Review), Alerting-Konfiguration, "
            "Audit-Trail für administrative Aktionen."
        ),
    },
    {
        "id": "OWASP-PC-C10",
        "title": "Handle All Errors and Exceptions",
        "description": (
            "Fehler und Ausnahmen müssen zentral und sicher behandelt werden. "
            "Keine internen Details (Stack Traces, SQL-Fehler) an den Benutzer "
            "zurückgeben. Fehlerzustände sollen in einen sicheren Zustand überführen."
        ),
        "cra_articles": ["Anhang I Part I Nr. 4", "Anhang I Part I Nr. 6"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Globaler Exception-Handler, generische Fehlermeldungen im Frontend, "
            "kein Stack-Trace im HTTP-Response (produktiv), "
            "Error-Monitoring (Sentry o. ä.), Logging von Fehlern server-side."
        ),
    },
]
