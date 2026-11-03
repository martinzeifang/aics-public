# Abweichungen, Nichtanwendbarkeit und offene Umsetzung

Dieses Dokument ist die Gegenprobe zum übrigen Dossier. Es sagt, was **nicht**
erfüllt ist — und in welcher der drei Kategorien es steht, die rechtlich etwas
Verschiedenes bedeuten.

!!! info "Warum es drei Kategorien sind und nicht eine Liste"
    Ein Prüfer fragt nicht „was fehlt", sondern „warum fehlt es". Die Antworten
    „die Anforderung trifft auf dieses Produkt nicht zu", „sie trifft zu, das
    Restrisiko ist abgewogen und angenommen" und „sie trifft zu und ist noch
    nicht umgesetzt" haben verschiedene Rechtsfolgen. Sie in einer Liste zu
    führen würde die erste schwächer und die dritte besser aussehen lassen, als
    sie ist.

| Kategorie | Rechtliche Grundlage | Wirkung auf die Konformität |
|---|---|---|
| **A — nicht anwendbar** | Art. 13 Abs. 4: Begründung in der technischen Dokumentation | konform |
| **B — begründete Abweichung, Restrisiko angenommen** | risikobasierte Bewertung nach Art. 13 Abs. 2 und 3 | konform, solange die Begründung trägt und die Wiedervorlage eingehalten wird |
| **C — offene Umsetzung** | — | **nicht konform**, bis erledigt |

Für Kategorie C gibt es keine Beschönigung. Sie steht hier, damit sie sichtbar
bleibt, und nicht, damit sie als abgehandelt gilt.

## Gemessener Stand

Gerechnet am **2. November 2026** über `cra/konformitaet_gate.evaluate` auf der
Produktivinstallation, Fassung 8.3.0:

| | |
|---|---|
| Anforderungen im Katalog | **36** |
| erfüllt (≥ 4 von 5) | **18** |
| begründet akzeptiert | **3** |
| offen | **15** |
| Anhang VII vollständig belegt | **ja** |
| EU-Konformitätserklärung ausgestellt | **ja** |
| **offene Punkte mit roter Wirkung** | **0** |
| Ampel | **rot** |

!!! info "Die letzten zwei Zeilen gehören zusammen gelesen"
    Die Ampel ist rot **wegen der Zahl offener Anforderungen, nicht wegen einer
    Nicht-Konformität**. Es gibt keinen einzigen Punkt mit roter Wirkung — die
    beiden gerechneten offenen Punkte (ungeprüfte KI-Entwürfe im
    Anforderungsregister, Testnachweis älter als die letzte
    Funktionsaktualisierung) wirken je **bedingt**.

    Das ist ein Unterschied, auf den es ankommt: Eine rote Wirkung bedeutet,
    dass das Produkt oder ein festgelegtes Verfahren einer grundlegenden
    Anforderung **nicht genügt**. Davon liegt nichts vor. Was vorliegt, sind
    Anforderungen, deren Erfüllung noch nicht auf 4 von 5 bewertet ist, und
    die vierzehn Positionen der Kategorie C.

!!! info "Dieses Dokument ist Teil der technischen Dokumentation"
    Die Begründungen der Kategorie A sind das, was Art. 13 Abs. 4 verlangt: eine
    klare Begründung **in der technischen Dokumentation**, wenn eine
    grundlegende Anforderung nicht anwendbar ist. Die Kategorien B und C gehören
    zur Risikobewertung nach Abs. 2 und 3.

    Es ist bewusst **veröffentlicht** und nicht nur intern geführt. Wer ein
    Werkzeug für Nachweisakten verkauft und seine eigene Akte beschönigt, hat
    sein Produkt widerlegt. Der Preis ist, dass hier Schwächen stehen; der
    Gewinn ist, dass ein Betreiber sie in seine eigene Risikobetrachtung
    aufnehmen kann — bei B2 ist das ausdrücklich nötig.

    **Was nicht hier steht**, sind Angaben über den Härtungszustand der eigenen
    Server. Sie sind eine Betriebsangabe und kein Produktmerkmal; auf einer
    öffentlichen Seite wären sie eine Wegbeschreibung. Sie liegen in einem
    Betriebsvermerk und werden einer Behörde auf Verlangen vorgelegt.

---

## A — Nicht anwendbar (Art. 13 Abs. 4)

### A1 · Automatische Installation von Sicherheitsaktualisierungen

| | |
|---|---|
| **Fundstelle** | Anhang I Teil I Nr. 2 Buchst. c · Anhang I Teil II Nr. 7 |
| **Anforderung** | Sicherheitsaktualisierungen, „gegebenenfalls" automatisch als Standardeinstellung installiert |

Der Wortlaut nennt die automatische Installation mit dem Vorbehalt
„**gegebenenfalls**"; Nr. 2 des Teils I steht insgesamt unter „soweit
zutreffend", und Teil II Nr. 7 wiederholt das „gegebenenfalls".

**Begründung:** Die AI Compliance Suite ist eine serverseitige Anwendung, die
der Betreiber in seiner eigenen Umgebung betreibt. Es gibt keinen Fernzugriff des
Herstellers, und es soll keinen geben — ein Weg, auf dem der Hersteller ungefragt
Abbilder in fremden Umgebungen austauschen kann, ist ein Weg, den auch ein
anderer benutzen kann. Ein Austausch bedeutet zudem einen Neustart der Dienste
und eine Schemaanlage an fremden Daten; wann das stattfindet, entscheidet
derjenige, der die Verfügbarkeit zusagt.

**Was stattdessen erfüllt ist** (die zweite Hälfte des Buchst. c, die *ohne*
Vorbehalt steht): Nutzer werden über verfügbare Aktualisierungen unterrichtet,
und sie können den Zeitpunkt frei bestimmen. Einzelheiten:
[Aktualisierungen, Signaturprüfung und Rückfall](update-und-rueckfall.md).

| | |
|---|---|
| **Entschieden** | 2. November 2026, Inhaber |
| **Überprüfung** | jährlich und bei jeder Änderung der Auslieferungsform |

### A2 · Vier-Augen-Prinzip bei Freigaben im eigenen Haus

| | |
|---|---|
| **Fundstelle** | keine — die Verordnung verlangt keine Rollentrennung |
| **Betroffen** | die eigene Werbeaussage und die Funktion, die das Produkt für Kunden erzwingt |

Die Suite erzwingt für ihre Nutzer: wer einen Konformitätsnachweis einreicht,
gibt ihn nicht frei. Mit einer Person ist diese Trennung nicht herstellbar.

**Das steht hier, weil es sonst jemandem auffällt**, der die Werbeaussage neben
die Praxis legt. Ersetzt wird die Trennung durch Nachvollziehbarkeit: Jede
Freigabe trägt Person und Zeitpunkt im fortschreibungssicheren Revisionspfad.
Das ist weniger als eine Trennung und mehr als nichts — und es ist der Grund,
warum B1 unten als Risiko geführt wird.

---

## B — Begründete Abweichungen mit angenommenem Restrisiko

### B1 · Keine Vertretung benannt

| | |
|---|---|
| **Betroffen** | IMPL-01 · ART13-05 · ART13-08 · ART13-09 · ART14-01 bis ART14-03 |
| **Fundstelle** | Art. 13 Abs. 21 bis 23, Art. 14 Abs. 1 bis 4 |

**Was nicht erfüllt ist:** Alle Pflichten mit Frist hängen an der Erreichbarkeit
einer Person. Die 24-Stunden-Frist der Frühwarnung nach Art. 14 Abs. 1 kennt
keinen Urlaub und keine Krankheit.

**Risiko:** Eine versäumte Meldefrist ist eine unmittelbare Verletzung des
Art. 14 — und zwar die einzige Pflicht dieses Dossiers, die **heute schon gilt**
(Art. 71 Abs. 2, seit 11. September 2026). Dazu die Folge für
[ART13-09](einstellung-betriebstaetigkeit.md): Bei dauerhafter Verhinderung des
Inhabers löst niemand die Unterrichtung der Betreiber aus.

**Ausgleichende Maßnahmen** — sie verringern das Risiko, beseitigen es nicht:

| Maßnahme | Wirkung |
|---|---|
| Die Anlaufstelle ist ein Postfach, nicht eine Person; es wird arbeitstäglich gelesen | eine Meldung geht nicht verloren, auch wenn die Reaktion wartet |
| Der Ablauf steht geschrieben: Kriterien, Fristen, Empfänger, Rückfallweg | wer einspringt, muss nichts erfinden |
| Fristen und Empfänger werden in der Anwendung geführt, nicht im Kopf | der Vorgang ist von außen nachvollziehbar |
| Der Zugang zur Meldeplattform wird vor jedem Release geprüft | die Frist geht nicht für die Beschaffung des Zugangs verloren |

**Restrisiko:** hoch. Es wird angenommen, weil die Alternative — eine
Vertretung, die es nicht gibt, zu behaupten — eine Falschangabe wäre.

| | |
|---|---|
| **Angenommen von** | Martin Zeifang, Inhaber |
| **Angenommen am** | 2. November 2026 |
| **Wiedervorlage** | **spätestens 31. März 2027** — und damit deutlich vor dem Geltungsbeginn am 11. Dezember 2027. Art. 14 gilt bereits; die Frist ist knapp gesetzt und nicht am Geltungsbeginn ausgerichtet |
| **Mögliche Formen** | eine zweite Person mit Zugang zu Anlaufstelle und Meldeplattform · eine vertragliche Vertretung · eine Vereinbarung mit einem Dienstleister für die Annahme und Weiterleitung |

### B2 · Dateien im Ruhezustand werden nicht verschlüsselt

| | |
|---|---|
| **Betroffen** | AI1-04 |
| **Fundstelle** | Anhang I Teil I Nr. 2 Buchst. e — Vertraulichkeit gespeicherter Daten, „z. B. durch Verschlüsselung" |

**Was nicht erfüllt ist:** Eine Sicherung ist ein vollständiger Abzug des
Datenbestands — alle Mandanten, alle Nachweisdokumente, die Benutzertabelle, die
Live-Konfiguration. Sie liegt unverschlüsselt im Dateisystem und lässt sich
herunterladen.

!!! success "Im Produkt behoben, in dieser Installation noch nicht eingeschaltet"
    Seit Fassung 8.4.0 kann die Anwendung ihre Sicherungen verschlüsseln
    (`AICS_BACKUP_KEY`, AES-256-GCM blockweise, Format `AICSBAK1`). Das
    beseitigt die **Produkteigenschaft**, die diese Abweichung begründet hat —
    nicht aber ihre Wirkung hier: Eingeschaltet ist sie in dieser Installation
    nicht (`enabled: false`, gemessen unten).

    Drei Entscheidungen daran gehören in die Akte, weil sie die Zusage tragen:

    * **Kein Rückfall** auf `AICS_AT_REST_KEY` oder `JWT_SECRET_KEY` — die
      Lehre aus B6. Ein Schlüssel, der aus der Installation abgeleitet wird,
      liegt mit den Daten im selben Korb.
    * **Fehlt der Schlüssel, scheitert die Sicherung**, und zwar bevor etwas
      geschrieben wird. Ein unverschlüsseltes Archiv, das für verschlüsselt
      gehalten wird, ist schlimmer als ein offen unverschlüsseltes.
    * **Das Format ist offen dokumentiert**, in einer Beilegedatei im Klartext
      neben jedem Archiv. Sonst widerspräche die Verschlüsselung der
      Zehnjahresfrist aus Art. 13 Abs. 13 — ein Archiv, das nur eine bestimmte
      Fassung einer bestimmten Anwendung lesen kann, taugt nicht für die
      Aufbewahrung (Festlegung 4 in [Aufbewahrung](aufbewahrung.md)).

    Das Einschalten ist eine **Betriebsentscheidung** mit Schlüsselverwaltung
    und bleibt deshalb hier geführt, bis es getan ist.

!!! danger "Gemessen, nicht angenommen — es betrifft mehr als die Sicherungen"
    Fassung 1.0 dieses Dokuments nannte nur die Sicherungsarchive. Die Messung
    in der Produktivinstallation am 2. November 2026 ergibt mehr:

    | Einstellung bzw. Messung | Stand |
    |---|---|
    | `security.at_rest_encryption.enabled` | **false** |
    | `encrypt_evidence` | false |
    | `encrypt_backups` | true — wirkt aber nur bei `enabled` |
    | `AICS_AT_REST_KEY` gesetzt | **nein** |
    | Dateien mit `.enc` unter `data/` | **0** |

    Die At-Rest-Verschlüsselung ist damit **nicht teilweise, sondern gar nicht**
    in Betrieb: Auch die hochgeladenen Nachweisdokumente der Mandanten liegen
    im Klartext. Die Fähigkeit steckt im Produkt
    (`shared/crypto_at_rest.py`, `evidence/db.py`) und ist abgeschaltet.

    **Was dagegen wirkt** und nicht kleingeredet werden soll: die
    Feldverschlüsselung einzelner Geheimnisse (Präfix `AICSFLD1:` — in der
    Produktivakte nachweisbar an den hinterlegten Zugangstoken), die
    Transportverschlüsselung und die Rechtevergabe auf dem Datenträger.
    Das sind andere Maßnahmen, keine Ersatzmaßnahmen für Buchst. e.

    Diese Unterscheidung ist der Grund, warum der Punkt hier und nicht in der
    Kategorie A steht: Nicht anwendbar ist er nicht — er ist nicht eingeschaltet.

**Risiko:** Wer Dateizugriff auf den Datenträger erlangt — über einen
Datenträger, der das Haus verlässt, über ein Sicherungsmedium, über einen
Einbruch in das Wirtssystem —, liest den gesamten Mandantenbestand. Bei einem
Werkzeug, das Nachweisakten für Dritte führt, ist das der schwerste denkbare
Vertraulichkeitsverlust.

!!! warning "Hinweis an den Betreiber"
    Diese Abweichung betrifft **jede** Installation, auch Deine. Eine
    Verschlüsselung des Datenträgers oder des Dateisystems, auf dem das
    Sicherungsverzeichnis liegt, ist derzeit die wirksamste Gegenmaßnahme und
    liegt beim Betreiber. Sie ist unabhängig von diesem Produkt einzurichten.

    Dass die Anwendung Sicherungen unverschlüsselt ablegt, ist eine
    Produkteigenschaft, die in die eigene Risikobetrachtung des Betreibers
    eingeht — nach Art. 32 DSGVO genauso wie nach dem CRA. Sie steht deshalb
    hier und nicht nur in einer internen Liste.

**Ausgleichende Maßnahmen:**

| Maßnahme | Wirkung |
|---|---|
| Feldverschlüsselung der empfindlichsten Inhalte (Zugangstoken, TOTP-Geheimnisse, Zugangsschlüssel) | diese Felder sind auch in einem erbeuteten Archiv unlesbar |
| Nachweisdateien liegen verschlüsselt (`.enc`) | die hochgeladenen Kundendokumente sind geschützt |
| Herunterladen nur mit Verwaltungsrecht, mit Eintrag im Revisionspfad samt Handelnden | ein Abzug ist nachvollziehbar |
| Betrieb auf eigener Infrastruktur, nicht bei einem Anbieter | kein fremder Zugriff auf die Datenträger |
| Zugang zum Wirtssystem nur über Schlüssel, kein Kennwort | der Weg zum Dateizugriff ist verengt |

**Was ausdrücklich nicht als ausgleichend gilt:** Berichtsexporte im Klartext.
Ein Bericht **ist** das Lieferobjekt — er wird gelesen, versandt, einer Behörde
vorgelegt. Ihn zu verschlüsseln würde den Abruf brechen, ohne etwas zu schützen,
das nicht ohnehin herausgehen soll. Der ernste Fall sind die Dateien, die
*dauerhaft* liegen, und das sind Archiv und Nachweisablage.

**Restrisiko:** mittel bis hoch — hoch, sobald ein Archivstand nach
[Aufbewahrung](aufbewahrung.md) an einem zweiten Ort liegt. Genau dann ist
„unverschlüsselt" keine Randnotiz mehr, und deshalb ist die Verschlüsselung
Voraussetzung für den zweiten Ort und nicht eine Verbesserung danach.

| | |
|---|---|
| **Angenommen von** | Martin Zeifang, Inhaber |
| **Angenommen am** | 2. November 2026 |
| **Wiedervorlage** | **vor der Einrichtung des zweiten Aufbewahrungsorts**, spätestens 30. Juni 2027 |
| **Vorgesehene Lösung** | eine einzige Öffnungsstelle für verschlüsselte und unverschlüsselte Archive, erkannt am Dateikopf statt an der Endung; Altarchive bleiben einspielbar, sonst nimmt die Änderung dem Betrieb seinen Rückweg |
| **Sofort möglich, ohne Änderung am Produkt** | Verschlüsselung des Datenträgers oder Dateisystems durch den Betreiber. Schließt die Abweichung nicht, verringert das Hauptrisiko erheblich |

### B3 · Keine Prüfsummen in der Abhängigkeitsliste der Python-Pakete

| | |
|---|---|
| **Betroffen** | IMPL-03 |
| **Fundstelle** | Art. 13 Abs. 5 — gebotene Sorgfalt bei Komponenten Dritter |

**Was nicht erfüllt ist:** Die Abhängigkeitsliste nennt Mindestfassungen, keine
festen Fassungen mit Prüfsummen. Zwei Bauläufe mit demselben Quellstand können
damit verschiedene Pakete ziehen.

**Risiko:** Ein Baulauf zieht eine andere Fassung als der vorige — unbemerkt bei
einem zurückgezogenen oder übernommenen Paket. Das ist der Angriffsweg über die
Lieferkette, der in den letzten Jahren am häufigsten funktioniert hat.

**Ausgleichende Maßnahmen:**

| Maßnahme | Wirkung |
|---|---|
| Basis-Abbilder sind auf Digest festgelegt, mit lesbarem Zeiger daneben | die Grundlage des Bauslaufs ist reproduzierbar |
| Abhängigkeiten werden in vier Ökosystemen automatisch überwacht und angehoben | eine Lücke wird gemeldet, nicht eingefroren |
| Schwachstellenprüfung der Abhängigkeiten in jedem Baulauf | eine bekannte Lücke bricht den Baulauf |
| Stückliste je Fassung und Artefakt, signiert am Digest | **was tatsächlich enthalten war, ist nachträglich feststellbar** — das ist die wichtigste der Maßnahmen |
| Aufnahmeprüfung vor der Integration neuer Komponenten | siehe [Lieferkette](lieferkette.md) |

Die vierte Zeile verdient die Hervorhebung: Die Stückliste macht aus der
Abweichung ein *feststellbares* Risiko statt eines unbemerkten. Wer wissen will,
welche Fassung in einem ausgelieferten Abbild steckt, kann es aus der
Attestierung am Digest ermitteln — ohne uns zu fragen.

**Warum nicht einfach eingeführt:** Eine Sperrdatei mit Prüfsummen braucht einen
festen Platz im Bauprozess (`--require-hashes`) und einen dokumentierten Weg,
sie bei jeder Änderung neu zu erzeugen. **Halb eingeführt wäre sie schlechter
als gar nicht**, weil der Bauprozess dann zwei Wahrheiten über die
Abhängigkeiten hätte — und die Abweichung zwischen ihnen fiele erst auf, wenn
jemand sie vergleicht.

| | |
|---|---|
| **Angenommen von** | Martin Zeifang, Inhaber |
| **Angenommen am** | 2. November 2026 |
| **Wiedervorlage** | **30. September 2027** — vor dem Geltungsbeginn |
| **Restrisiko** | mittel |

### B4 · Signaturprüfung in der Schaltfläche der Anwendung abgeschaltet

| | |
|---|---|
| **Betroffen** | AI2-07 |
| **Fundstelle** | Anhang I Teil II Nr. 7 |

**Was nicht erfüllt ist:** Die Aktualisierungsschaltfläche in der Anwendung
prüft die Herkunftskennung, nicht die Signatur. Das Prüfwerkzeug liegt nicht im
Abbild.

**Risiko:** Wer über die Schaltfläche aktualisiert, verlässt sich auf eine
Kennung, die beim Bau gesetzt wird und nicht kryptografisch gebunden ist.

**Ausgleichende Maßnahmen:** Der **vorgesehene** Deploy-Weg ist das
Betriebsskript, und das prüft seit Fassung 8.3.1 standardmäßig Herkunft *und*
Signatur, bevor ein Dienst angefasst wird. Jeder Betreiber kann die Signatur
außerdem selbst prüfen; der Aufruf steht in
[Aktualisierungen und Rückfall](update-und-rueckfall.md).

**Warum nicht geschlossen:** Eine Schaltfläche, die immer mit einem
Werkzeugfehler endet, ist schlechter als eine benannte Lücke — sie sieht aus wie
eine Prüfung und ist keine.

| | |
|---|---|
| **Angenommen von** | Martin Zeifang, Inhaber |
| **Angenommen am** | 2. November 2026 |
| **Wiedervorlage** | 30. September 2027 |
| **Restrisiko** | niedrig für den dokumentierten Weg, mittel für die Schaltfläche |

### B5 · Keine durchgehende Erreichbarkeit, nur ein Kommunikationsmittel

| | |
|---|---|
| **Betroffen** | ART14-03 · ART13-07 |
| **Fundstelle** | Art. 13 Abs. 17 — die Anlaufstelle lässt die Wahl des Mittels und ist nicht auf automatisierte Instrumente beschränkt |

**Was nicht erfüllt ist:** Eine Erreichbarkeit rund um die Uhr gibt es nicht.
Angeboten ist als schneller Kanal **nur** E-Mail; eine Rufnummer ist nicht
veröffentlicht.

**Was erfüllt ist:** Die Anlaufstelle wird von einer Person gelesen und ist
damit kein automatisiertes Instrument. Postalisch ist der Hersteller über die
veröffentlichte Anschrift erreichbar — ein zweiter, nicht automatisierter Weg,
aber kein schneller.

**Die Verordnung verlangt keine 24/7-Erreichbarkeit.** Sie verlangt, dass
Fristen eingehalten werden; das ist B1. Dass die 24/7-Erreichbarkeit in der
Eigenbewertung als Lücke auftaucht, stammt aus einem Umsetzungshinweis und nicht
aus dem Verordnungstext — der Hinweis ist gute Praxis, keine Pflicht.

| | |
|---|---|
| **Angenommen von** | Martin Zeifang, Inhaber |
| **Angenommen am** | 2. November 2026 |
| **Wiedervorlage** | 31. März 2027, gemeinsam mit B1 |
| **Schließt beides** | die Angabe einer Rufnummer — sie erfüllt die Wahlmöglichkeit und zugleich die offene Angabe im Impressum nach § 5 DDG |
| **Restrisiko** | niedrig |

---

### B6 · Der At-Rest-Schlüssel wird aus dem Sitzungsgeheimnis abgeleitet

| | |
|---|---|
| **Betroffen** | AI1-04 |
| **Fundstelle** | Anhang I Teil I Nr. 2 Buchst. e — Vertraulichkeit gespeicherter Daten |

**Was nicht erfüllt ist:** Die Feldverschlüsselung einzelner Geheimnisse
(Zugangstoken, TOTP-Geheimnisse, Zugangsschlüssel; Präfix `AICSFLD1:`) leitet
ihre Passphrase in der Reihenfolge `AICS_AT_REST_KEY` → `JWT_SECRET_KEY` ab.
In der Produktivinstallation ist **`AICS_AT_REST_KEY` nicht gesetzt**, also
hängt die Verschlüsselung am Sitzungsgeheimnis.

**Das Problem ist nicht die Stärke des Schlüssels** — `JWT_SECRET_KEY` ist ein
zufälliges 64-Zeichen-Geheimnis wie jedes andere. Das Problem ist die
**Kopplung zweier Lebenszyklen.** Ein Sitzungsgeheimnis wird gewechselt: nach
einem Verdacht, bei einem Personalwechsel, routinemäßig. Ein At-Rest-Schlüssel
darf das nicht, solange verschlüsselte Felder in der Datenbank liegen.

!!! danger "Hinweis an den Betreiber — und an mich selbst"
    **`JWT_SECRET_KEY` auf einer bestehenden Installation nicht wechseln.** Wer
    es tut, um Sitzungen zu entwerten, zerstört damit lautlos die gespeicherten
    Zugangstoken, die Portainer-Schlüssel **und die Mehrfaktor-Anmeldung aller
    Konten** — `decrypt_field` kann einen Fehlschlag nicht von „war nie
    verschlüsselt" unterscheiden. Es gibt keine Fehlermeldung.

    Dasselbe gilt für jeden Weg, auf dem die Datei `/app/data/.jwt-secret`
    ersetzt oder neu erzeugt wird.

**Was wirkt, und was gerade nicht wirkt:**

| Schutz | Stand |
|---|---|
| Warnung im Log beim ersten Verschlüsseln (`_warne_vor_dem_rueckfall`, #1915) | **wirkt** — in der Produktivinstallation nachweisbar im Log |
| Fail-closed-Riegel ohne eigenen Schlüssel (`_guard_at_rest_encryption`, #1189) | **wirkt hier nicht** — er greift nur bei `at_rest_encryption.enabled`, und das steht auf `false` (siehe B2) |
| Kein statischer Vorgabeschlüssel mehr (#1179) | wirkt |

Die zweite Zeile ist der Punkt: Der Riegel ist vorhanden und richtig gebaut,
aber er prüft eine Einstellung, die abgeschaltet ist — während der Pfad, der
tatsächlich benutzt wird, nur eine Log-Zeile hat. Ein Schutz, der an der
falschen Bedingung hängt, ist in der Akte so viel wert wie keiner.

**Das günstige Zeitfenster ist vorbei.** Die Warnung sagt, das Setzen eines
eigenen Schlüssels sei kostenlos, „solange noch keine verschlüsselten Felder
bestehen". Es bestehen welche. Das Nachziehen braucht jetzt eine
**Umschlüsselung**, und die ist der Grund, warum dieser Punkt als begründete
Abweichung und nicht als Sofortmaßnahme geführt wird.

| | |
|---|---|
| **Angenommen von** | Martin Zeifang, Inhaber |
| **Angenommen am** | 2. November 2026 |
| **Wiedervorlage** | 31. März 2027, gemeinsam mit B2 |
| **Ausgleichend** | das Geheimnis liegt dauerhaft in `/app/data/.jwt-secret` und wird beim Neustart nicht neu erzeugt; es wird also nicht versehentlich gewechselt |
| **Schließt es** | eigener `AICS_AT_REST_KEY` samt Umschlüsselung der bestehenden Felder |
| **Restrisiko** | mittel — nicht wegen eines Angreifers, sondern wegen eines Betriebsvorgangs, der wie Routine aussieht |

---

## C — Offene Umsetzung (nicht konform, bis erledigt)

Hier steht keine Begründung, sondern ein Termin. Was in dieser Tabelle steht,
ist nicht erfüllt, und das Dossier behauptet nichts anderes.

| Nr. | Anforderung | Was fehlt | Fällig | Wer |
|---|---|---|---|---|
| **C0** | ART13-03 · ART13-07 · AI2-06 · AI2-08 | **Die öffentlichen Angaben stehen unter einer anderen Adresse als der, die die Akte nennt.** Erreichbar sind sie unter `www.zeifang-lai.de`; zitiert werden sie überall als `cyberwoks.de`, und dort liefert der Anbieter für *jeden* Pfad seine Parkseite — mit **HTTP 200**. Die `security.txt` ist dadurch formal unwirksam | **vorrangig** | Inhaber |
| **C1** | IMPL-06 | Der erste Schulungszyklus nach [Schulung und Awareness](../security/awareness.md) ist nicht durchlaufen. Das Konzept erfüllt die Anforderung nicht; der Nachweis entsteht erst durch die Durchführung. **Baustein 1 (CRA-Grundlagen) ist über eine Qualifikation abdeckbar** — siehe das Register dort; dann verkleinert sich dieser Punkt auf die Bausteine 2 bis 4 und die Phishing-Erkennung, er entfällt nicht | **31. Dezember 2026** | Inhaber |
| **C2** | IMPL-05 | Es gibt keinen Archivstand je Fassung und keinen zweiten Aufbewahrungsort. Die nächtliche Sicherung hält fünf Stände — das ist Wiederanlauf, nicht Aufbewahrung | **31. März 2027**, zweiter Ort nach B2 | Inhaber |
| **C3** | AI2-07 | Der Rückfalltest ist nicht durchgeführt. Skript liegt bereit (`~/werkzeuge/rueckfalltest-dev.sh`) | **30. November 2026** | Inhaber |
| **C4** | ART14-01 · ART14-02 | Der Zugang zur einheitlichen Meldeplattform ist nicht eingerichtet, und der Trockenlauf der Meldekette ist nicht durchgeführt. **Diese Pflicht gilt bereits** | **31. Dezember 2026** | Inhaber |
| **C5** | AI2-06 | Security Advisories sind im öffentlichen Quellverzeichnis nicht aktiviert; es ist keines veröffentlicht. Die Richtlinie dazu steht seit `SECURITY.md` Fassung 2.0 | **30. November 2026** | Inhaber |
| **C6** | AI2-08 | Keine Teilnahme an einem Austauschformat (etwa Allianz für Cyber-Sicherheit oder die Meldeplattform des nationalen CSIRT) | **31. März 2027** | Inhaber |
| **C7** | ART13-03 | Der Unterstützungszeitraum steht nicht in der Angebotsvorlage. Art. 13 Abs. 19 verlangt die Angabe **zum Zeitpunkt des Kaufs** | **30. November 2026** | Inhaber |
| **C8** | ART13-03 | Eine Mitteilung in der Anwendung bei Erreichen des Endes des Unterstützungszeitraums (Art. 13 Abs. 19 Satz 2, „soweit technisch machbar" — bei einer Webanwendung ist sie machbar) | **vor Oktober 2031**, geplant mit der Fassung, die den Zeitraum verlängert oder beendet | Inhaber |
| **C9** | ART13-09 | Vorsorge für den Fall dauerhafter Verhinderung des Inhabers; der Adressbestand der Betreiber trägt keine Kontaktadresse für Betriebsmitteilungen | **31. März 2027**, gemeinsam mit B1 | Inhaber |
| **C10** | übergreifend | Die Wirtssysteme der eigenen Installationen sind gegen die Härtungsvorgaben zu prüfen — Stand der Betriebssystemunterstützung und Verschlüsselung der Datenträger. Das betrifft nicht das Produkt, sondern den Betrieb; hier fällt beides auf denselben zusammen. Einzelheiten im Betriebsvermerk, nicht in diesem Dokument | **31. März 2027** | Inhaber |
| **C11** | ART13-06 | Die laufende Anwendung kennt ihren eigenen **Digest** nicht — `APP_IMAGE_DIGEST` ist deklariert und wird von keinem Baulauf gesetzt, weil der Digest erst nach dem Bau feststeht. Art. 13 Abs. 15 ist davon **nicht** berührt (die Fassungsangabe genügt); für einen Betreiber, der einen Vorfall dokumentieren muss, fehlt aber die genaueste Angabe. Lösung: beim Deploy ermitteln und ablegen, nicht ins Abbild backen | **30. Juni 2027** | Inhaber |
| **C12** | AI2-06 · ART13-07 | **Die veröffentlichte Sicherheitsrichtlinie war nicht die der Akte.** Unter der Adresse, die das Schwachstellenregister als Meldekanal nennt, lag eine 344 Byte lange Fassung mit einer **privaten** Mailadresse und Zusagen von 48 Stunden und 7 Tagen — beides enger als die eigene Richtlinie. Ursache war ein Schritt im Veröffentlichungslauf, der die Datei nach dem Abgleich überschrieb; er ist entfernt und durch einen Wächter ersetzt. **Am 2. November 2026 von Hand nachgezogen** — die öffentliche Fassung ist seither byte-gleich mit dem Quellstand, ebenso die Advisory-Vorlage. Offen bleibt der Nachweis, dass der **automatische** Weg trägt; er läuft erst bei der nächsten Freigabe | **nächste Freigabe** | Inhaber |
| **C13** | ART13-07 | Die Herstellerangaben sind öffentlich nicht einheitlich: Website und Akte nennen `kontakt@cyberwoks.de`, die öffentliche Produktbeschreibung und die Lizenzanleitung nennen für denselben Hersteller eine private Mailadresse. Art. 13 Abs. 15 und 16 verlangen *eine* Kontaktstelle; zwei Adressen in zwei öffentlichen Dokumenten sind keine | **31. Dezember 2026** | Inhaber |

!!! danger "Zu C0 — nachgemessen am 2. November 2026"
    | Adresse | Antwort | Inhalt |
    |---|---|---|
    | `https://www.zeifang-lai.de/cra.html` | 200 | **die richtige Seite** — „CRA-Informationen — AI Compliance Suite" |
    | `https://www.zeifang-lai.de/.well-known/security.txt` | 200 | die richtige Datei |
    | `https://cyberwoks.de/` | 200 | Parkseite des Anbieters, `<title>` leer, `robots: noindex,nofollow` |
    | `https://cyberwoks.de/cra.html` | **200** | dieselbe Parkseite — **nicht** die Informationen nach Anhang II |
    | `https://cyberwoks.de/.well-known/security.txt` | **200** | dieselbe Parkseite als HTML |

    **Die Angaben sind also veröffentlicht — nur nicht dort, wo die Akte sie
    verortet.** Das ist etwas anderes als „fehlt", und es ist in einer
    Nachweisakte nicht besser: Die Internetadresse der EU-Konformitätserklärung,
    `support_end_kaufhinweis_url` und `update_zusagen_nachweis` nennen alle
    `cyberwoks.de`. Wer dort nachsieht — ein Kunde, ein Prüfer — findet eine
    Parkseite und schließt daraus, dass es die Angaben nicht gibt.

    **Die 200 ist dabei schlimmer als eine 404.** Eine 404 sagt einem Werkzeug
    „gibt es nicht". Eine 200 mit HTML sagt ihm „hier ist Deine `security.txt`"
    und liefert etwas, das kein Parser lesen kann. Dieselbe Fehlerklasse, die
    dieses Projekt als „es wird das Falsche gelesen" führt — nur von außen.

    **Die `security.txt` ist dadurch an beiden Enden unwirksam.** Sie trägt
    `Canonical: https://cyberwoks.de/.well-known/security.txt`. Nach RFC 9116
    dient dieses Feld dem Abrufer zur Prüfung, dass er die Datei an der
    vorgesehenen Stelle gefunden hat; stimmt die Abrufadresse mit keinem
    `Canonical` überein, ist der Inhalt nicht zu verwenden. Heute gilt beides:
    Am Fundort (`zeifang-lai.de`) stimmt das Feld nicht, und an der Adresse im
    Feld (`cyberwoks.de`) liegt keine `security.txt`.

    **Zwei Ebenen, und beide zählen:**

    1. **Rechtlich** greift Art. 13 Abs. 18 mit dem Geltungsbeginn am
       11. Dezember 2027. Bis dahin ist das kein Rechtsverstoß.
    2. **In der eigenen Akte zählen diese Adressen heute als Nachweis.** Ein
       Nachweis, der auf eine Parkseite auflöst, ist kein Nachweis — und er
       sieht in der Akte wie einer aus.

    **Wie weit die Umstellung ist** — erhoben am 2. November 2026:

    | Name | zeigt auf | Antwort |
    |---|---|---|
    | `cyberwoks.de` | `217.160.0.222` (Anbieter) | 200, Parkseite |
    | `www.cyberwoks.de` | **kein Eintrag** | löst nicht auf |
    | `aics.cyberwoks.de` | `zeifang-lai.ddns.net` | 302 — **die Anwendung** |
    | `aisuite.cyberwoks.de` | `martinzeifang.github.io` | 200 — **das Handbuch** |

    Zwei der vier Namen sind also längst richtig delegiert. Offen sind der
    Hauptname und `www`.

    Deshalb steht C0 vor C1 und trägt kein Datum, sondern „vorrangig": Es ist
    die einzige Position der Liste, die **mehrere** Anforderungen auf einmal von
    „belegt" auf „unbelegt" dreht, und sie kostet keine Arbeit am Produkt — zwei
    Einträge im Namensdienst und die vorgeschaltete Prüfschicht.

    Dabei zu beachten: Die Zusage in § 4 der Datenschutzerklärung — keine
    vollständige IP-Adresse — **muss die vorgeschaltete Schicht mittragen**,
    sonst ist sie falsch. `robots.txt` bleibt auf `Disallow: /`, solange die
    Angaben nach § 5 DDG im Impressum offen sind. Und die `security.txt` darf
    ihr `Canonical` erst dann auf `cyberwoks.de` zeigen lassen, wenn sie dort
    auch liegt — sonst bleibt sie unwirksam, nur in der anderen Richtung.

### Was C **nicht** enthält

Zwei Dinge, die in früheren Bewertungen als Lücke geführt wurden und keine sind:

**„Die Live-Datenbanken liegen unverschlüsselt vor."** Die Angabe stammt aus
einer Zeit, in der die Anwendung auf SQLite-Dateien lief. Sie läuft seit Juni
2026 auf PostgreSQL; die genannten Dateien sind tote Reste. Was bleibt, ist B2 —
und das ist das Archiv, nicht die laufende Datenbank. Eine Lücke, die es nicht
mehr gibt, in einer Akte zu führen, beschädigt die Akte: Sie lenkt die
Aufmerksamkeit von B2 ab.

**„Die Katalogreferenz von ART13-05 ist falsch."** Sie war es und ist mit
Fassung 8.3.1 berichtigt: ART13-05 verweist auf Art. 13 Abs. 22. Insgesamt
wurden dabei 38 Fundstellen in vier Katalogen berichtigt.

---

## Wie eine Abweichung in der Akte wirksam wird

Dieses Dokument ist die **Begründung**. Es ist nicht die Stelle, an der das
Gate sie liest — und diese Trennung ist kein Mangel, sondern Absicht.

`cra/konformitaet_gate.evaluate` zählt eine Anforderung unter der Schwelle nur
dann als *begründet akzeptiert* statt als *offen*, wenn in der **verknüpften
Risikobewertung** ein Risiko zu dieser Anforderung liegt. Verknüpft wird über
`felder._source_id = "cra:requirement:<ID>"`.

| Feld | Wer verlangt es | Inhalt |
|---|---|---|
| `behandlung` | **das Gate** | `akzeptiert` |
| `akzeptanz_kategorie` | **das Gate** | `restrisiko` · `kompensierend` · `nicht_anwendbar` |
| `akzeptanz_grund` | der Schreibweg | die Begründung — in Worten, nicht zirkulär |
| `akzeptanz_von` / `_am` | die Sorgfalt | wer, wann |
| `akzeptanz_review` | die Sorgfalt | Wiedervorlage |
| `rechtsgrundlage` | die Sorgfalt | die Fundstelle |

!!! warning "Die zweite Spalte ist der wichtigste Teil dieser Tabelle"
    Fassung 1.0 führte alle sechs Felder als Voraussetzung auf. Das ist
    **falsch** und verharmlost die Lage: `_accepted_gap_for` prüft genau
    **zwei** Dinge — `behandlung == "akzeptiert"` und eine nichtleere
    `akzeptanz_kategorie`. Grund, Person, Datum, Wiedervorlage und
    Rechtsgrundlage liest es **nicht**.

    Daraus folgt der Satz, der die drei Befunde unten erst gefährlich macht:
    **Eine inhaltlich falsche Begründung schaltet die Ampel genauso um wie eine
    richtige.** Das Gate kann Begründungen nicht bewerten — es kann nur zählen,
    ob eine Entscheidung getroffen wurde. Die Richtigkeit zu prüfen ist die
    Aufgabe eines Menschen, und dieses Dokument ist die Stelle, an der das
    nachvollziehbar wird.

    Messbare Folge am 2. November 2026: In der Akte liegen zwölf Akzeptanzen,
    vier davon mit Bezug auf eine CRA-Anforderung, und **bei keiner** ist
    `akzeptanz_review` oder `rechtsgrundlage` gefüllt. Drei zählen trotzdem als
    begründet akzeptiert.

Dass die Begründung dort steht und nicht hier, ist richtig: Sie ist die
**Annahme eines Restrisikos durch eine namentlich benannte Person**, mit Datum
und im Revisionspfad. Ein Dokument kann das nicht leisten — es trägt keine
Unterschrift.

!!! info "Umgekehrt gilt es auch: ohne Risiko kein Wirksamwerden"
    Zu **AI1-04** liegt in der verknüpften Risikobewertung *kein* Risiko mit
    der Quelle `cra:requirement:AI1-04` — gemessen, null Zeilen. B2 ist damit
    zwar hier begründet, wirkt in der Akte aber **nicht**: Die Anforderung
    bleibt *offen*, gleichgültig wie gut dieses Dokument sie beschreibt.

    Dasselbe gilt für B1, B3, B5 und B6. Ein Verzeichnis begründeter Abweichungen,
    dessen Einträge nicht als Akzeptanz in der Risikobewertung stehen, ist eine
    Absichtserklärung und kein Nachweis.

!!! danger "Drei Begründungen in der Akte halten nicht"
    Nachgelesen am 2. November 2026. In der Akte liegen vier Akzeptanzen **mit
    Bezug auf eine CRA-Anforderung** (von zwölf insgesamt), und **keine** trägt
    eine Rechtsgrundlage oder eine Wiedervorlage. Drei tragen
    eine Begründung, die einem Prüfer auffällt:

    | Anforderung | Eingetragen | Woran es scheitert |
    |---|---|---|
    | **ART13-05** | „Für die Anwendung ist keine Kooperation erforderlich" | **Das ist das Gegenteil der Rechtslage.** Art. 13 Abs. 22 verpflichtet *jeden* Hersteller zur Vorlage von Unterlagen und zur Zusammenarbeit; eine Ausnahme gibt es nicht. Eine solche Begründung liest sich als Verkennung der eigenen Pflicht |
    | **AI2-07** | „das Restrisiko wird akzeptiert" | zirkulär — sagt, *dass* akzeptiert wird, nicht *warum*. Eine Begründung, die nur die Entscheidung wiederholt, begründet nichts |
    | **IMPL-06** | „Schulung nicht notwendig, da keine Anwender", Kategorie `nicht_anwendbar` | verkennt die Anforderung: Gemeint sind die an **Entwicklung und Betrieb beteiligten Personen** (Art. 13 Abs. 1, Cybersicherheitskultur), nicht die Anwender des Produkts. [Schulung und Awareness](../security/awareness.md) nennt die Rollen ausdrücklich — eine Schulung *ist* notwendig |

    **Warum das schwerer wiegt als ein offener Punkt:** Eine offene Anforderung
    ist ein Versäumnis. Eine falsche Begründung ist eine **Rechtsposition**, und
    sie hält das Gate zugleich grün — bei IMPL-06 steht in der Akte „nicht
    anwendbar", während die Bewertung daneben 2/5 und ein Schulungskonzept mit
    offenem ersten Zyklus ausweist. Das ist Fail-Open durch eine Begründung,
    nicht durch eine Lücke.

    **IMPL-06 ist keine Abweichung**, sondern **C1** — offene Umsetzung mit
    Termin. Die Akzeptanz dort gehört zurückgenommen, nicht umformuliert.

    Ersatztexte für die fünf Abweichungen dieses Dokuments liegen in
    `~/werkzeuge/risiko-akzeptanz-texte.md`, je mit Kategorie,
    Rechtsgrundlage und Wiedervorlage. Eingetragen werden sie von der Person,
    die das Restrisiko trägt — nicht von einem Werkzeug.

## Pflege dieses Dokuments

| Prüfung | Turnus |
|---|---|
| Jede Wiedervorlage in B: ist der Termin erreicht, trägt die Begründung noch? | vierteljährlich, in der Durchsicht nach [Governance](governance.md) |
| Jeder Termin in C: erledigt, verschoben (mit Grund) oder überfällig? | vierteljährlich |
| Nichtanwendbarkeit in A: hat sich die Auslieferungsform geändert? | jährlich und bei jeder wesentlichen Änderung |

Eine überschrittene Wiedervorlage in B macht aus der Abweichung eine
**Nicht-Konformität** — die Annahme eines Restrisikos gilt für den Zeitraum, für
den sie erklärt wurde, und nicht auf Dauer. Das ist der Satz, der dieses
Dokument davor bewahrt, eine Ablage für Unbequemes zu werden.

**Fassung 1.6, 2. November 2026.** Gegenüber Fassung 1.5 ist bei **B2** ergänzt,
dass die Anwendung ihre Sicherungen seit 8.4.0 verschlüsseln kann. Die
Abweichung wird deshalb **nicht gestrichen**: Was zählt, ist der Zustand dieser
Installation, nicht die Fähigkeit des Produkts — und dort ist die
Verschlüsselung aus.

Fassung 1.5 zog **C12** nach: Die
öffentliche Sicherheitsrichtlinie ist von Hand richtiggestellt und byte-gleich mit dem
Quellstand; offen bleibt allein der Nachweis, dass der automatische Weg trägt. Ein
Eintrag, der eine behobene Lage weiter als offen beschreibt, ist derselbe Schaden wie
einer, der eine offene Lage als behoben ausgibt — nur in die andere Richtung.

Fassung 1.4 teilte **C1**: Der
Prüfpunkt IMPL-06 verlangt Wissen zu zwei Gegenständen, und der regulatorische ist
über eine geprüfte Qualifikation belegbar. Die Regel dazu steht in
[Schulung und Awareness](../security/awareness.md) — einschließlich der Grenze, dass
eine Qualifikation **kein** Konformitätsnachweis ist und nicht in die Nähe der
Konformitätsaussage gehört.

Fassung 1.3 ergänzte **B6** — die
Feldverschlüsselung leitet ihren Schlüssel aus `JWT_SECRET_KEY` ab, und der
fail-closed-Riegel dagegen greift hier nicht, weil er an einer abgeschalteten
Einstellung hängt. Der Punkt stand in Fassung 1.2 noch als „von der KI falsch
beschrieben“ — nachgemessen im Produktivlog traf die KI zu und meine
Entkräftung nicht.

Fassung 1.2 erweiterte **B2** —
gemessen ist die At-Rest-Verschlüsselung nicht teilweise, sondern gar nicht in
Betrieb (`enabled: false`, null `.enc`-Dateien), es betrifft also auch die
Nachweisdokumente und nicht nur die Sicherungen. Berichtigt ist außerdem die
Beschreibung des Gate-Mechanismus: Es prüft **zwei** Felder, nicht sechs — eine
falsche Begründung schaltet die Ampel wie eine richtige. Dazu der Hinweis, dass
B1, B2, B3 und B5 in der Akte **nicht wirksam** sind, solange kein Risiko mit der
entsprechenden Quelle als akzeptiert eingetragen ist.

Fassung 1.1 ergänzte **C12**
(die veröffentlichte Sicherheitsrichtlinie war nicht die der Akte) und **C13**
(zwei öffentliche Kontaktadressen für denselben Hersteller); C10 und C11 standen
in der falschen Reihenfolge. Fundstellen: Art. 13 Abs. 2 und 3
(Risikobewertung), Abs. 4 (Begründung bei Nichtanwendbarkeit), Abs. 5, 15 und 16
(Herstellerangaben und Kontaktstelle), Abs. 17, 19, 21 bis 23, Art. 14,
Art. 71 Abs. 2 (Geltungsbeginn der Meldepflichten),
Anhang I Teil I Nr. 2 Buchst. c und e, Anhang I Teil II Nr. 7 der Verordnung
(EU) 2024/2847. Gegen die amtliche deutsche Fassung geprüft
(ABl. L vom 20.11.2024).
