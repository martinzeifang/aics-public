# AI-Act-Dossier der AI Compliance Suite

Dieses Dossier dokumentiert, wie die **AI Compliance Suite (AICS) selbst** die Anforderungen
des EU AI Act (Verordnung (EU) 2024/1689) adressiert. Es ist aus der AI-Act-Bewertung der
Suite im eigenen AI-Act-Modul entstanden (Gap-Issues #1547–#1559) und dient als Nachweis
für Betreiber, Prüfer und Kunden.

> Hinweis: Dies ist keine Rechtsberatung. Die Einordnung ist vom Anbieter verantwortlich
> zu prüfen und bei wesentlichen Änderungen zu aktualisieren (siehe [Change-Management](qms-change-management.md)).

## Einordnung

| Frage | Einordnung |
|---|---|
| Rolle | **Anbieter** eines Software-Produkts, das KI-Modelle **integriert** (kein eigenes Modelltraining). Betreiber ist die jeweils einsetzende Organisation. |
| KI-Komponenten | Vortrainierte Sprachmodelle über eine Provider-Schicht: **lokal** via Ollama (Standard, `ai.provider = on_prem`) oder **Cloud** (OpenAI-kompatible API bzw. Anthropic) nur nach ausdrücklicher Freigabe (`ai.cloud.allow_data_egress`). |
| Zweckbestimmung | Assistenz bei Compliance-Aufgaben: Bewertungsentwürfe, Dokumentationsvorschläge, Zusammenfassungen. Entscheidungen trifft immer ein Mensch. |
| Art. 5 (verbotene Praktiken) | Nicht einschlägig — keine Manipulation, kein Social Scoring, keine Biometrie, keine Emotionserkennung. |
| Hochrisiko (Art. 6, Anhang III) | **Nein.** Die Zweckbestimmung fällt unter keinen Anhang-III-Bereich (insb. keine Beschäftigungs-, Zugangs- oder Kreditentscheidungen über natürliche Personen) und die Suite ist kein Sicherheitsbauteil nach Anhang I. |
| GPAI (Art. 51 ff.) | AICS ist **kein** GPAI-Modell, sondern nutzt solche Modelle nachgelagert. Pflichten der Modellanbieter bleiben bei diesen. |
| Anwendbare Pflichten | **Art. 4** (KI-Kompetenz der Nutzenden — Unterstützung über das Literacy-Register), **Art. 50** (Transparenz: Kennzeichnung KI-generierter Inhalte). |
| Freiwillige Umsetzung | Die Hochrisiko-Anforderungen (Art. 9–17, 72–73) werden **freiwillig** als Qualitätsmaßstab umgesetzt (Art. 95, Verhaltenskodizes). Dieses Dossier belegt den Stand. |

## Zuordnung der Anforderungen

| AICS-ID | Anforderung | Artikel | Nachweis | Issue |
|---|---|---|---|---|
| AIA-HR-01 | Risikomanagement-System | Art. 9 | [Risikomanagement](risikomanagement.md) | #1547 |
| AIA-HR-02 | Daten-Governance und Datenqualität | Art. 10 | [Daten-Governance](daten-governance.md) | #1548 |
| AIA-HR-03 | Technische Dokumentation | Art. 11, Anhang IV | [Technische Dokumentation](technische-dokumentation.md) | #1549 |
| AIA-HR-04 | Logging / Record-Keeping | Art. 12 | [Logging](logging.md) | #1550 |
| AIA-HR-05 | Transparenz und Nutzerinformationen | Art. 13, Art. 50 | [Transparenz](transparenz.md) | #1551 |
| AIA-HR-06 | Menschliche Aufsicht | Art. 14 | [Menschliche Aufsicht](menschliche-aufsicht.md) | #1552 |
| AIA-HR-07 | Genauigkeit, Robustheit, Cybersicherheit | Art. 15 | [Robustheit & Cybersicherheit](robustheit-cybersicherheit.md) | #1553 |
| AIA-GOV-01 | Qualitätsmanagementsystem | Art. 17 | [QMS & Change-Management](qms-change-management.md) | #1554 |
| AIA-GOV-02 | Change-/Configuration-Management | Art. 17 Abs. 1 b, c | [QMS & Change-Management](qms-change-management.md) | #1555 |
| AIA-DATA-01 | Datasets: Dokumentation und Lineage | Art. 10 Abs. 2 | [Daten-Governance](daten-governance.md) | #1556 |
| AIA-DATA-02 | Bias-/Fairness-Prüfungen | Art. 10 Abs. 2 f, g | [Daten-Governance](daten-governance.md) | #1557 |
| AIA-HR-08 | Post-Market-Monitoring | Art. 72 | [Marktbeobachtung & Vorfälle](marktbeobachtung-vorfaelle.md) | #1558 |
| AIA-HR-09 | Incident-Management / Meldungen | Art. 73 | [Marktbeobachtung & Vorfälle](marktbeobachtung-vorfaelle.md) | #1559 |

## Pflege

- **Verantwortlich:** Produktverantwortliche:r der AICS (Freigabe siehe [QMS](qms-change-management.md#freigabe)).
- **Aktualisierung:** bei jedem Release mit KI-relevanter Änderung (neuer Provider, neue KI-Funktion,
  geänderte Datenflüsse) sowie mindestens jährlich.
- Die Bewertung der Suite im eigenen AI-Act-Modul wird nach jeder Aktualisierung neu durchgeführt;
  verbleibende Lücken werden wieder als Issues erfasst.
