"""MITRE ATT&CK Enterprise-Referenz für die SOC-Coverage-Heatmap (#1321/#1349).

Umfassende (nicht vollständige) Technik-Liste je Taktik — deckt insbesondere die
Techniken ab, die das Wazuh-Standardregelwerk mappt, damit die Regelwerk-basierte
Coverage (#1349) realistisch ist. Techniken, die hier (noch) fehlen, werden von
``soc.detection.attack_coverage`` dennoch über die Union aller im Regelwerk/in
Alarmen gefundenen Techniken angezeigt (Fallback-Taktik „Sonstige").
"""
from __future__ import annotations

import re

# Taktik-Reihenfolge (ATT&CK Enterprise Kill-Chain) + Fallback „Sonstige".
TACTICS: list[tuple[str, str]] = [
    ("TA0043", "Reconnaissance"),
    ("TA0042", "Resource Development"),
    ("TA0001", "Initial Access"),
    ("TA0002", "Execution"),
    ("TA0003", "Persistence"),
    ("TA0004", "Privilege Escalation"),
    ("TA0005", "Defense Evasion"),
    ("TA0006", "Credential Access"),
    ("TA0007", "Discovery"),
    ("TA0008", "Lateral Movement"),
    ("TA0009", "Collection"),
    ("TA0011", "Command and Control"),
    ("TA0010", "Exfiltration"),
    ("TA0040", "Impact"),
    ("TA0000", "Sonstige"),
]

# technique_id -> (Name, Taktik-Name). Eine Technik wird ihrer primären Taktik
# zugeordnet (ATT&CK listet manche unter mehreren).
TECHNIQUES: dict[str, tuple[str, str]] = {
    # Reconnaissance
    "T1595": ("Active Scanning", "Reconnaissance"),
    "T1592": ("Gather Victim Host Information", "Reconnaissance"),
    "T1589": ("Gather Victim Identity Information", "Reconnaissance"),
    # Resource Development
    "T1583": ("Acquire Infrastructure", "Resource Development"),
    "T1584": ("Compromise Infrastructure", "Resource Development"),
    "T1586": ("Compromise Accounts", "Resource Development"),
    "T1587": ("Develop Capabilities", "Resource Development"),
    "T1588": ("Obtain Capabilities", "Resource Development"),
    # Initial Access
    "T1566": ("Phishing", "Initial Access"),
    "T1190": ("Exploit Public-Facing Application", "Initial Access"),
    "T1133": ("External Remote Services", "Initial Access"),
    "T1078": ("Valid Accounts", "Initial Access"),
    # Execution
    "T1059": ("Command and Scripting Interpreter", "Execution"),
    "T1204": ("User Execution", "Execution"),
    "T1053": ("Scheduled Task/Job", "Execution"),
    "T1047": ("Windows Management Instrumentation", "Execution"),
    "T1106": ("Native API", "Execution"),
    "T1203": ("Exploitation for Client Execution", "Execution"),
    "T1559": ("Inter-Process Communication", "Execution"),
    "T1569": ("System Services", "Execution"),
    # Persistence
    "T1136": ("Create Account", "Persistence"),
    "T1543": ("Create or Modify System Process", "Persistence"),
    "T1547": ("Boot or Logon Autostart Execution", "Persistence"),
    "T1546": ("Event Triggered Execution", "Persistence"),
    "T1098": ("Account Manipulation", "Persistence"),
    "T1137": ("Office Application Startup", "Persistence"),
    "T1176": ("Browser Extensions", "Persistence"),
    "T1505": ("Server Software Component", "Persistence"),
    "T1574": ("Hijack Execution Flow", "Persistence"),
    # Privilege Escalation
    "T1068": ("Exploitation for Privilege Escalation", "Privilege Escalation"),
    "T1548": ("Abuse Elevation Control Mechanism", "Privilege Escalation"),
    # Defense Evasion
    "T1070": ("Indicator Removal", "Defense Evasion"),
    "T1027": ("Obfuscated Files or Information", "Defense Evasion"),
    "T1562": ("Impair Defenses", "Defense Evasion"),
    "T1112": ("Modify Registry", "Defense Evasion"),
    "T1036": ("Masquerading", "Defense Evasion"),
    "T1055": ("Process Injection", "Defense Evasion"),
    "T1014": ("Rootkit", "Defense Evasion"),
    "T1140": ("Deobfuscate/Decode Files or Information", "Defense Evasion"),
    "T1207": ("Rogue Domain Controller", "Defense Evasion"),
    "T1218": ("System Binary Proxy Execution", "Defense Evasion"),
    "T1222": ("File and Directory Permissions Modification", "Defense Evasion"),
    "T1484": ("Domain or Tenant Policy Modification", "Defense Evasion"),
    "T1497": ("Virtualization/Sandbox Evasion", "Defense Evasion"),
    "T1550": ("Use Alternate Authentication Material", "Defense Evasion"),
    # Credential Access
    "T1110": ("Brute Force", "Credential Access"),
    "T1003": ("OS Credential Dumping", "Credential Access"),
    "T1555": ("Credentials from Password Stores", "Credential Access"),
    "T1040": ("Network Sniffing", "Credential Access"),
    "T1212": ("Exploitation for Credential Access", "Credential Access"),
    "T1552": ("Unsecured Credentials", "Credential Access"),
    "T1556": ("Modify Authentication Process", "Credential Access"),
    "T1557": ("Adversary-in-the-Middle", "Credential Access"),
    # Discovery
    "T1087": ("Account Discovery", "Discovery"),
    "T1018": ("Remote System Discovery", "Discovery"),
    "T1046": ("Network Service Discovery", "Discovery"),
    "T1083": ("File and Directory Discovery", "Discovery"),
    "T1012": ("Query Registry", "Discovery"),
    "T1016": ("System Network Configuration Discovery", "Discovery"),
    "T1033": ("System Owner/User Discovery", "Discovery"),
    "T1057": ("Process Discovery", "Discovery"),
    "T1082": ("System Information Discovery", "Discovery"),
    "T1120": ("Peripheral Device Discovery", "Discovery"),
    "T1135": ("Network Share Discovery", "Discovery"),
    "T1518": ("Software Discovery", "Discovery"),
    "T1526": ("Cloud Service Discovery", "Discovery"),
    # Lateral Movement
    "T1021": ("Remote Services", "Lateral Movement"),
    "T1570": ("Lateral Tool Transfer", "Lateral Movement"),
    "T1072": ("Software Deployment Tools", "Lateral Movement"),
    "T1210": ("Exploitation of Remote Services", "Lateral Movement"),
    # Collection
    "T1005": ("Data from Local System", "Collection"),
    "T1560": ("Archive Collected Data", "Collection"),
    "T1074": ("Data Staged", "Collection"),
    "T1113": ("Screen Capture", "Collection"),
    "T1114": ("Email Collection", "Collection"),
    "T1115": ("Clipboard Data", "Collection"),
    "T1119": ("Automated Collection", "Collection"),
    "T1213": ("Data from Information Repositories", "Collection"),
    "T1530": ("Data from Cloud Storage", "Collection"),
    # Command and Control
    "T1071": ("Application Layer Protocol", "Command and Control"),
    "T1105": ("Ingress Tool Transfer", "Command and Control"),
    "T1572": ("Protocol Tunneling", "Command and Control"),
    "T1001": ("Data Obfuscation", "Command and Control"),
    "T1090": ("Proxy", "Command and Control"),
    "T1092": ("Communication Through Removable Media", "Command and Control"),
    "T1095": ("Non-Application Layer Protocol", "Command and Control"),
    "T1102": ("Web Service", "Command and Control"),
    # Exfiltration
    "T1041": ("Exfiltration Over C2 Channel", "Exfiltration"),
    "T1048": ("Exfiltration Over Alternative Protocol", "Exfiltration"),
    "T1567": ("Exfiltration Over Web Service", "Exfiltration"),
    "T1537": ("Transfer Data to Cloud Account", "Exfiltration"),
    # Impact
    "T1486": ("Data Encrypted for Impact", "Impact"),
    "T1490": ("Inhibit System Recovery", "Impact"),
    "T1498": ("Network Denial of Service", "Impact"),
    "T1489": ("Service Stop", "Impact"),
    "T1485": ("Data Destruction", "Impact"),
    "T1499": ("Endpoint Denial of Service", "Impact"),
    "T1529": ("System Shutdown/Reboot", "Impact"),
    "T1531": ("Account Access Removal", "Impact"),
    "T1561": ("Disk Wipe", "Impact"),
    "T1565": ("Data Manipulation", "Impact"),
}

_TID_RE = re.compile(r"^T\d{4}$")


def normalize_technique(tid: str) -> str:
    """``T1566.001`` → ``T1566`` (Sub-Technik auf Basistechnik). Ungültige/leere
    Werte → ``""`` (z. B. Variablen-Platzhalter aus Custom-Regeln)."""
    base = (tid or "").strip().upper().split(".")[0]
    return base if _TID_RE.match(base) else ""


def technique_name(tid: str) -> str:
    norm = normalize_technique(tid)
    return TECHNIQUES.get(norm, (norm or tid, ""))[0]
