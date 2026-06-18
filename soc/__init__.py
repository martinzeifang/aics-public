"""SOC-Modul — Security Operations Center.

Reiner Triage-/Ticket-Layer für **Wazuh-Alarme** (kein SIEM-Nachbau): Alarme ab
einstellbarem Level bewerten (was ist das / False Positive / echt), Reaktion
dokumentieren, echte Incidents führen und je nach betroffenem Asset die
einschlägigen Meldepflichten (DSGVO Art. 33/34, NIS2 Art. 23, CRA Art. 14,
AI-Act Art. 73) automatisch auslösen.

Sprint #29 / Epic #1254.
"""
