"""OWASP Proactive Controls (v3) - checklist metadata with CRA article mapping."""

from __future__ import annotations

from typing import Any


OWASP_PC_V3: list[dict[str, Any]] = [
    {
        "id": "OWASP-PC-C1",
        "description_en": (
            "Security requirements must be defined and documented explicitly as "
            "part of the development process — for example as user stories, "
            "threat models or security checklists. Without formal requirements "
            "there is no basis for any further security measure."
        ),
        "evidence_hint_en": (
            "SECURITY.md, threat model document, security requirements list, risk "
            "assessment (e.g. STRIDE), security user stories in the backlog."
        ),
        "title": "Define Security Requirements",
        "description": (
            "Sicherheitsanforderungen müssen explizit als Teil des Entwicklungsprozesses "
            "definiert und dokumentiert werden – z. B. als User Stories, Threat Models oder "
            "Security Checklisten. Ohne formale Anforderungen fehlt die Grundlage für alle "
            "weiteren Sicherheitsmaßnahmen."
        ),
        "cra_articles": ["Anhang I Teil I Nr. 1", "Art. 13 Abs. 1", "Art. 13 Abs. 5"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "SECURITY.md, Threat-Model-Dokument, Security-Anforderungsliste, "
            "Risikobewertung (z. B. STRIDE), Security-User-Stories im Backlog."
        ),
    },
    {
        "id": "OWASP-PC-C2",
        "description_en": (
            "Rather than implementing security functions yourself, use vetted and "
            "actively maintained libraries (for cryptography, authentication, "
            "validation). Home-grown implementations are error-prone and hard to "
            "audit."
        ),
        "evidence_hint_en": (
            "Dependency management policy, SBOM (software bill of materials), "
            "list of security libraries in use, Renovate/Dependabot "
            "configuration, vulnerability scan report (e.g. Trivy, Snyk)."
        ),
        "title": "Leverage Security Frameworks and Libraries",
        "description": (
            "Statt Sicherheitsfunktionen selbst zu implementieren, sollen geprüfte und "
            "aktiv gepflegte Bibliotheken (z. B. für Kryptografie, Auth, Validierung) "
            "eingesetzt werden. Eigene Implementierungen sind fehleranfällig und schwer "
            "auditierbar."
        ),
        "cra_articles": ["Anhang I Teil I Nr. 2 Buchst. a", "Anhang I Teil II Nr. 1"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Dependency-Management-Policy, SBOM (Software Bill of Materials), "
            "Liste genutzter Security-Libraries, Renovate/Dependabot-Konfiguration, "
            "Vulnerability-Scan-Report (z. B. Trivy, Snyk)."
        ),
    },
    {
        "id": "OWASP-PC-C3",
        "description_en": (
            "Database access must use least privilege. SQL injection is prevented "
            "by parameterised queries. Credentials must not appear in source "
            "code."
        ),
        "evidence_hint_en": (
            "Parameterised queries / ORM use in the code, dedicated database "
            "users without admin rights, secret management (Vault, env secrets), "
            "no cleartext password in the repository (secret scan report)."
        ),
        "title": "Secure Database Access",
        "description": (
            "Datenbankzugriffe müssen mit minimalen Rechten (Least Privilege) erfolgen. "
            "SQL-Injection wird durch parametrisierte Abfragen verhindert. Zugangsdaten "
            "dürfen nicht im Quellcode stehen."
        ),
        "cra_articles": ["Anhang I Teil I Nr. 2 Buchst. d und e"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Parametrisierte Queries / ORM-Nutzung im Code, dedizierte DB-User "
            "ohne Admin-Rechte, Secret-Management (Vault, Env-Secrets), "
            "kein Klartext-Passwort im Repository (Secret-Scan-Report)."
        ),
    },
    {
        "id": "OWASP-PC-C4",
        "description_en": (
            "Output to browsers, shells, XML parsers and the like must be encoded "
            "for its context in order to prevent XSS, injection and similar "
            "attacks. Templates should have auto-escaping enabled."
        ),
        "evidence_hint_en": (
            "Template engine with auto-escaping enabled (e.g. Jinja2, React JSX), "
            "output encoding policy, SAST report (no XSS findings), code review "
            "checklist."
        ),
        "title": "Encode and Escape Data",
        "description": (
            "Ausgaben an Browser, Shell, XML-Parser etc. müssen kontextabhängig kodiert "
            "werden um XSS, Injection und ähnliche Angriffe zu verhindern. "
            "Templates sollen Auto-Escaping aktiviert haben."
        ),
        "cra_articles": ["Anhang I Teil I Nr. 2 Buchst. f"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Template-Engine mit aktiviertem Auto-Escape (z. B. Jinja2, React JSX), "
            "Output-Encoding-Richtlinie, SAST-Report (keine XSS-Findings), "
            "Code-Review-Checkliste."
        ),
    },
    {
        "id": "OWASP-PC-C5",
        "description_en": (
            "All input from outside (users, APIs, files, environment variables) "
            "must be checked for type, format and range before it is processed. "
            "Validation must take place on the server side."
        ),
        "evidence_hint_en": (
            "Schema validation (JSON Schema, Pydantic, Zod), server-side "
            "validation logic, fuzzing results, SAST report on injection "
            "findings."
        ),
        "title": "Validate All Inputs",
        "description": (
            "Alle Eingaben von außen (Benutzer, APIs, Dateien, Umgebungsvariablen) "
            "müssen vor der Verarbeitung auf Typ, Format und Bereich geprüft werden. "
            "Die Validierung muss serverseitig erfolgen."
        ),
        "cra_articles": ["Anhang I Teil I Nr. 2 Buchst. a und f"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Schema-Validierung (JSON Schema, Pydantic, Zod), serverseitige "
            "Validierungslogik, Fuzzing-Ergebnisse, SAST-Report auf Injection-Findings."
        ),
    },
    {
        "id": "OWASP-PC-C6",
        "description_en": (
            "Authentication and identity management must be implemented securely: "
            "strong passwords/MFA, secure session handling, no home-grown "
            "authentication protocols."
        ),
        "evidence_hint_en": (
            "MFA configuration, password policy (NIST 800-63B), session timeout, "
            "OAuth2/OIDC integration, FIDO2/WebAuthn support, authentication "
            "library (no custom auth code)."
        ),
        "title": "Implement Digital Identity",
        "description": (
            "Authentifizierung und Identitätsmanagement müssen sicher implementiert sein: "
            "starke Passwörter/MFA, sichere Session-Verwaltung, keine selbst entwickelten "
            "Auth-Protokolle."
        ),
        "cra_articles": ["Anhang I Teil I Nr. 2 Buchst. d"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "MFA-Konfiguration, Passwort-Policy (NIST 800-63B), Session-Timeout, "
            "OAuth2/OIDC-Integration, FIDO2/WebAuthn-Support, "
            "Auth-Bibliothek (kein Custom-Auth-Code)."
        ),
    },
    {
        "id": "OWASP-PC-C7",
        "description_en": (
            "Authorisation checks must take place on the server side for every "
            "request (deny by default). Least privilege: users and services hold "
            "only the rights they actually need."
        ),
        "evidence_hint_en": (
            "Role model documentation, RBAC/ABAC implementation, server-side "
            "authorisation checks, penetration test report (IDOR tests), API "
            "access matrix."
        ),
        "title": "Enforce Access Controls",
        "description": (
            "Autorisierungsprüfungen müssen für jede Anfrage serverseitig erfolgen "
            "(Deny-by-Default). Least-Privilege-Prinzip: Nutzer und Dienste haben nur "
            "die minimal notwendigen Rechte."
        ),
        "cra_articles": ["Anhang I Teil I Nr. 2 Buchst. d"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Rollenmodell-Dokumentation, RBAC/ABAC-Implementierung, "
            "serverseitige Autorisierungschecks, Pentest-Report (IDOR-Tests), "
            "API-Zugriffsmatrix."
        ),
    },
    {
        "id": "OWASP-PC-C8",
        "description_en": (
            "Data must be protected both in transit (TLS) and at rest "
            "(encryption). Key management must be secure. No cleartext storage of "
            "sensitive data."
        ),
        "evidence_hint_en": (
            "TLS configuration (TLS 1.2 at minimum), encryption at rest (AES-256 "
            "or equivalent), key management system, secret scan report, data "
            "protection impact assessment (DPIA)."
        ),
        "title": "Protect Data Everywhere",
        "description": (
            "Daten müssen sowohl in der Übertragung (TLS) als auch im Ruhezustand "
            "(Verschlüsselung) geschützt sein. Schlüsselverwaltung muss sicher sein. "
            "Keine Klartextspeicherung sensibler Daten."
        ),
        "cra_articles": ["Anhang I Teil I Nr. 2 Buchst. e und f"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "TLS-Konfiguration (mind. TLS 1.2), Verschlüsselung at rest "
            "(AES-256 o. ä.), Key-Management-System, Secret-Scan-Report, "
            "Datenschutz-Folgenabschätzung (DSFA)."
        ),
    },
    {
        "id": "OWASP-PC-C9",
        "description_en": (
            "Security-relevant events (logins, errors, access attempts) must be "
            "logged — without sensitive data in the logs. Logs must be "
            "tamper-proof and fit for analysis."
        ),
        "evidence_hint_en": (
            "Logging concept, SIEM integration, security event definitions, no "
            "PII in logs (log review), alerting configuration, audit trail for "
            "administrative actions."
        ),
        "title": "Implement Security Logging and Monitoring",
        "description": (
            "Sicherheitsrelevante Ereignisse (Logins, Fehler, Zugriffsversuche) müssen "
            "protokolliert werden – ohne sensible Daten in den Logs. Logs müssen "
            "manipulationsgeschützt und auswertbar sein."
        ),
        "cra_articles": ["Anhang I Teil I Nr. 2 Buchst. l"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Logging-Konzept, SIEM-Integration, Security-Event-Definitionen, "
            "kein PII in Logs (Log-Review), Alerting-Konfiguration, "
            "Audit-Trail für administrative Aktionen."
        ),
    },
    {
        "id": "OWASP-PC-C10",
        "description_en": (
            "Errors and exceptions must be handled centrally and safely. Do not "
            "return internal details (stack traces, SQL errors) to the user. "
            "Error states should lead into a safe state."
        ),
        "evidence_hint_en": (
            "Global exception handler, generic error messages in the frontend, no "
            "stack trace in the HTTP response (in production), error monitoring "
            "(Sentry or equivalent), server-side logging of errors."
        ),
        "title": "Handle All Errors and Exceptions",
        "description": (
            "Fehler und Ausnahmen müssen zentral und sicher behandelt werden. "
            "Keine internen Details (Stack Traces, SQL-Fehler) an den Benutzer "
            "zurückgeben. Fehlerzustände sollen in einen sicheren Zustand überführen."
        ),
        "cra_articles": ["Anhang I Teil I Nr. 2 Buchst. h und k"],
        "ref": "https://owasp.org/www-project-proactive-controls/",
        "evidence_hint": (
            "Globaler Exception-Handler, generische Fehlermeldungen im Frontend, "
            "kein Stack-Trace im HTTP-Response (produktiv), "
            "Error-Monitoring (Sentry o. ä.), Logging von Fehlern server-side."
        ),
    },
]
