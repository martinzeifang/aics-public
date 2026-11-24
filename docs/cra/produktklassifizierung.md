# Produktklassifizierung und Bewertungsweg

Beantwortet die Anforderung **IMPL-04** der Eigenbewertung. Fundstellen: Art. 7 in
Verbindung mit Anhang III und IV (Einordnung), Art. 32 (Verfahren), Art. 3 Nr. 30
(wesentliche Änderung).

## Die Einordnung

| | |
|---|---|
| **Klasse** | Standardprodukt — weder wichtiges Produkt der Klasse I oder II nach Anhang III noch kritisches Produkt nach Anhang IV |
| **Bewertungsweg** | **Modul A** — interne Fertigungskontrolle nach Anhang VIII |
| Notifizierte Stelle | nicht vorgesehen, nicht beteiligt, keine Kennnummer |
| Entscheidung getroffen | 2. November 2026, Inhaber (siehe [Governance](governance.md)) |

## Begründung gegen Anhang III

Anhang III zählt die **wichtigen** Produkte auf. Die AI Compliance Suite ist in keiner der
Kategorien enthalten. Die Prüfung im Einzelnen — und zwar gegen die Kategorien, bei denen
eine Verwechslung naheliegt:

| Kategorie in Anhang III | Trifft zu? | Begründung |
|---|---|---|
| Identitätsverwaltungssysteme, Verwaltung privilegierter Zugänge | **nein** | Die Suite hat eine **eigene** Benutzerverwaltung für den Zugang zu sich selbst. Sie verwaltet keine Identitäten *für andere Systeme*, stellt keine Berechtigungen nach außen aus und ist kein Verzeichnisdienst. Das ist die Abgrenzung, auf die es hier ankommt: Eine Anwendung mit Anmeldung ist kein Identitätsverwaltungssystem. |
| Verwaltung und Schutz von Geheimnissen (Passwortmanager u. Ä.) | **nein** | Zugangstoken (Quellverzeichnis, Verwaltungsschnittstelle, KI-Anbieter) werden verschlüsselt gespeichert, weil die Anwendung sie **selbst** braucht. Sie bietet keine Verwahrung von Geheimnissen als Leistung an. |
| Systeme zur Überwachung oder Analyse von Netzverkehr, SIEM | **nein** | Nicht vorhanden. Eine frühere Komponente für Sicherheitsüberwachung (Alarm-Triage) wurde mit Fassung 8.3.0 **vollständig entfernt**; die Suite verarbeitet keine Telemetrie und keine Alarme mehr. |
| Netzverwaltungssysteme, Router, Firewalls, VPN | **nein** | Nicht vorhanden. |
| Betriebssysteme, Hypervisoren, Container-Laufzeiten, Bootmanager | **nein** | Die Suite wird *in* einem Container ausgeliefert; sie ist keine Laufzeitumgebung für andere. |
| Mikroprozessoren, Mikrocontroller, ASICs, FPGAs | **nein** | Keine Hardware. |
| Browser, Virenschutz, Verschlüsselungswerkzeuge | **nein** | Nicht vorhanden. Verschlüsselung wird intern verwendet, nicht als Werkzeug angeboten. |
| Smart-Home, industrielle Steuerungstechnik, IoT | **nein** | Keine Gerätesteuerung; der vorgesehene Einsatz schließt sicherheitskritische Steuerungstechnik ausdrücklich aus. |

## Begründung gegen Anhang IV

Anhang IV zählt die **kritischen** Produkte auf. Die Liste ist kurz und
abschließend — drei Positionen:

| Nr. | Position | Trifft zu? |
|---|---|---|
| 1 | Hardwaregeräte mit Sicherheitsboxen | **nein** — reine Software, kein Hardwareanteil |
| 2 | Smart-Meter-Gateways in intelligenten Messsystemen sowie andere Geräte für fortgeschrittene Sicherheitszwecke einschließlich der sicheren Kryptoverarbeitung | **nein** |
| 3 | Chipkarten oder ähnliche Geräte, einschließlich Sicherheitselemente | **nein** |

!!! info "Anhang IV ist nicht in Klassen gegliedert"
    Anders als Anhang III, der „Klasse I" und „Klasse II" unterscheidet, ist
    Anhang IV eine einfache Liste. Es gibt **keine** kritischen Produkte der
    Klasse I oder II.

    Das steht hier, weil die Anwendung selbst jahrelang zwei solche Klassen
    anbot: `critical_i` und `critical_ii` waren im Auswahlfeld die einzigen
    Einträge für kritische Produkte, und der Anforderungskatalog kannte beide
    nicht — ein so erfasstes Produkt fiel dort auf „Standardprodukt" zurück,
    und die Selbstbewertung nach Modul A galt als zulässig. Behoben mit #1919;
    die Alt-Schlüssel werden auf `critical` abgebildet, damit kein
    Bestandsdatensatz unspeicherbar wird.

## Was die Suite tatsächlich ist

Compliance-, Governance- und Dokumentationssoftware. Sie erfasst Anforderungen aus
Rechtsvorschriften, bewertet den Umsetzungsstand und erzeugt daraus Nachweise und
Berichte. Die Daten, die sie verarbeitet, sind **Aussagen über** Systeme — nicht die
Systeme selbst.

!!! info "Der Umstand, der die Einordnung nicht ändert, aber genannt sein muss"
    Die Suite enthält Nachweisdaten mehrerer Mandanten: Risikoregister, Lücken,
    Pentest-Befunde. Ein unbefugter Zugriff wäre für einen Angreifer wertvoll, weil er
    die Schwachstellen Dritter benennt.

    **Das macht das Produkt nicht zu einem wichtigen Produkt nach Anhang III** — die
    Einordnung folgt der Funktion, nicht der Vertraulichkeit der verarbeiteten Daten.
    Sonst wäre jede Datenbank ein wichtiges Produkt. Der Umstand ist dennoch kein
    Nebensatz: Er ist der Grund, warum die Anforderungen des Anhangs I hier mit demselben
    Ernst behandelt werden wie bei einem wichtigen Produkt, und er steht als bekanntes
    Risiko in den [CRA-Informationen Nr. 5](https://cyberwoks.de/cra.html).

## Zulässigkeit des Bewertungswegs

Für ein Standardprodukt ist Modul A — interne Fertigungskontrolle — zulässig. Art. 32
eröffnet daneben weitere Wege; sie sind hier nicht erforderlich:

| Weg | Für dieses Produkt |
|---|---|
| **Modul A** (interne Fertigungskontrolle) | **gewählt** — für ein Standardprodukt zulässig |
| Modul B+C (EU-Baumusterprüfung) | zulässig, aber nicht erforderlich |
| Modul H (umfassende Qualitätssicherung) | zulässig, aber nicht erforderlich |
| Europäisches Cybersicherheitszertifikat | nicht in Anspruch genommen |

Die Wahl des aufwendigeren Wegs wäre keine Verbesserung der Konformität, sondern eine
zusätzliche Prüfung durch einen Dritten. Sie bleibt möglich, falls ein Kunde sie verlangt;
dann wäre sie eine Vertriebs-, keine Konformitätsentscheidung.

!!! warning "Was der gewählte Weg verlangt"
    Modul A heißt: **Wir** prüfen, und wir legen die Prüfung nachvollziehbar ab. Es gibt
    keinen Dritten, dessen Prüfbericht Lücken auffängt. Die Last liegt vollständig auf
    der technischen Dokumentation nach Anhang VII und auf der Belastbarkeit der eigenen
    Bewertungen — ein Grund, warum in der Eigenbewertung „nicht belegt" ausdrücklich als
    „nicht erfüllt" zählt und nicht als Formfehler.

## Harmonisierte Normen

Zur Verordnung (EU) 2024/2847 sind **keine harmonisierten Normen** im Amtsblatt
veröffentlicht. Die Vermutungswirkung nach Art. 27 kann daher nicht in Anspruch genommen
werden; sie wird in der EU-Konformitätserklärung auch nicht behauptet.

Angewandt werden stattdessen technische Spezifikationen, die in der Erklärung einzeln
benannt sind. Dass sie **keine** harmonisierten Normen sind, ist Teil der Angabe — eine
Spezifikation, die als harmonisierte Norm aufgeführt wird, behauptet eine Rechtswirkung,
die nicht besteht.

## Überprüfung

| Anlass | Was geprüft wird |
|---|---|
| **Jede wesentliche Änderung** im Sinne des Art. 3 Nr. 30 | ob die Funktion die Einordnung berührt — vor allem, ob eine Fähigkeit hinzugekommen ist, die in Anhang III genannt wird |
| Jährlich | ob Anhang III oder IV geändert wurden, und ob harmonisierte Normen veröffentlicht sind |
| Bei neuer Funktion mit Bezug zu Identitäten, Geheimnissen, Netzverkehr oder Überwachung | Einordnung ausdrücklich erneut prüfen, **bevor** die Funktion ausgeliefert wird |

Die dritte Zeile ist die eigentliche Schutzvorkehrung. Die Einordnung als Standardprodukt
beruht darauf, dass die Suite **über** Systeme Aussagen trifft und nicht in sie eingreift.
Eine Funktion, die Berechtigungen in einem Kundensystem setzt oder Netzverkehr auswertet,
würde diese Grundlage verschieben — und sie würde sich unauffällig einführen lassen, weil
sie fachlich naheliegt.

Eine Sicherheitsaktualisierung ist **keine** wesentliche Änderung (Erwägungsgrund 39) und
löst diese Prüfung nicht aus.

**Fassung 1.0, 2. November 2026.** Fundstellen: Art. 7, Art. 27, Art. 32, Art. 3 Nr. 30,
Anhang III, Anhang IV, Anhang VIII der Verordnung (EU) 2024/2847.
