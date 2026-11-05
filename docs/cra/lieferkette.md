# Lieferkette und Fremdkomponenten

Beantwortet die Anforderung **IMPL-03** der Eigenbewertung. Fundstelle: Art. 13 Abs. 5 —
der Hersteller hat bei der Einbindung von Komponenten Dritter mit Sorgfalt zu verfahren
und sicherzustellen, dass sie die Cybersicherheit des Produkts nicht beeinträchtigen.

Die Software-Stückliste selbst ist kein Teil dieses Dokuments: Sie entsteht je Fassung
automatisch und hängt als signierte Attestation am Container-Abbild (siehe
[CRA-Informationen Nr. 9](https://cyberwoks.de/cra.html)). Hier steht, **wie entschieden
wird**, was überhaupt hineinkommt — und was heute noch fehlt.

## Prüfung vor der Aufnahme

Eine neue Abhängigkeit wird nicht aufgenommen, weil sie das Problem löst, sondern erst,
wenn die folgenden sechs Fragen beantwortet sind. Die Antworten gehören in den
Änderungsvorgang, der die Abhängigkeit einführt.

| Nr. | Frage | Abweisungsgrund |
|---|---|---|
| 1 | Wird sie gebraucht, oder löst die Standardbibliothek dasselbe? | Eine Abhängigkeit, die wenige Zeilen ersetzt, ist Angriffsfläche ohne Gegenwert. |
| 2 | Welche Lizenz, und ist sie mit der Auslieferung vereinbar? | unklare oder unvereinbare Lizenz |
| 3 | Wird sie gepflegt? Letzte Freigabe, Reaktion auf Sicherheitsmeldungen, Zahl der Beteiligten | seit über zwei Jahren keine Freigabe, keine erkennbare Sicherheitsarbeit |
| 4 | Bringt sie selbst viele weitere Abhängigkeiten mit? | ein Paket, das zwanzig weitere nachzieht, wird zur eigenen Lieferkette |
| 5 | Offene bekannte Schwachstellen? | offene kritische oder hohe Schwachstelle ohne Korrektur |
| 6 | Wie wird sie künftig überwacht? | kein Kanal, über den Schwachstellen bekannt werden |

Frage 6 ist die, die am leichtesten übersehen wird und am teuersten ist: Eine Komponente
ohne Überwachungsweg fällt bei der nächsten Schwachstelle niemandem auf. Für die
Bewertung der Fremdkomponenten im Release-Vorgang ist genau das die Angabe, die zählt —
die Suite gruppiert die Stückliste deshalb nach **Klasse und Ökosystem**, weil daran der
Versorgungsweg hängt: Ein Betriebssystempaket kommt über die Distribution und den Neubau
des Abbilds, ein Anwendungspaket über den Abhängigkeits-Abgleich und einen Release.

## Laufende Überwachung

| Quelle | Deckt ab | Turnus |
|---|---|---|
| Dependabot | **vier Ökosysteme** (#1915): Python (direkt und mittelbar), Frontend-npm (direkt, gruppiert), die Basis-Abbilder und die Arbeitsabläufe der Entwicklungsstrecke | wöchentlich |
| OSV-Scanner | Abhängigkeiten über Ökosysteme hinweg | geplanter Lauf in der Entwicklungsstrecke |
| `pip-audit` | Python | je Push und geplant |
| `npm audit` | Frontend-Abhängigkeiten | im Frontend-Bau |
| Schwachstellenabgleich der Suite | zieht Advisories und Dependabot-Befunde in das eigene Register des Produkts | täglich, zusätzlich auf Knopfdruck |
| Software-Stückliste je Fassung | 184 Komponenten der Anwendung, 70 des Webservers (Stand 8.3.0) | je Release |

Befunde laufen in das Schwachstellenregister des CRA-Moduls und von dort, soweit sie das
Produkt betreffen, in die Risikobewertung. Die Behandlung folgt den Fristen aus
[Offenlegung und Austausch](schwachstellen-offenlegung.md).

## Schutz der Lieferkette bei der Auslieferung

| Maßnahme | Stand |
|---|---|
| Abbilder werden aus einem **öffentlich einsehbaren Quellbaum** gebaut | umgesetzt |
| Schlüssellose Signatur der Release-Abbilder (Sigstore/cosign) | umgesetzt |
| Herkunftsnachweis (SLSA-Provenance, `mode=max`) | umgesetzt |
| Software-Stückliste als Attestation am Digest | umgesetzt |
| Betrieb ohne root, nur-lesendes Wurzeldateisystem möglich, abgelegte Capabilities | umgesetzt |
| Fremd-Abbilder im Betriebsverbund (Datenbank, PDF-Wandler, Zwischenspeicher) auf Fassungen festgelegt | umgesetzt — das Anheben ist bewusst eine Änderung am Quellcode und keine Nebenwirkung eines Updates |
| Das Deploy-Werkzeug prüft vor dem Einsetzen die **Herkunft** des Abbilds anhand der Quellangabe im Abbild | umgesetzt |
| Das Deploy-Werkzeug prüft zusätzlich die **cosign-Signatur** gegen die Identität des Veröffentlichungs-Ablaufs im öffentlichen Quellbaum | umgesetzt (#1915), auf der Befehlszeile **Vorgabe**; im Webdienst aus, weil im Abbild kein cosign liegt |
| Basis-Abbilder sind auf ihren **Digest** festgelegt — der Tag bleibt lesbar daneben stehen | umgesetzt (#1915) |

!!! warning "Herkunft ist nicht Signatur — und beides wird geprüft"
    Die Quellangabe in den Metadaten des Abbilds (`org.opencontainers.image.source`) ist
    eine Herkunfts*angabe*: Sie wird beim Bau gesetzt und ist nicht kryptografisch an das
    Abbild gebunden — wer ein Abbild baut, kann sie hineinschreiben. Erst die
    Signaturprüfung bindet das Abbild an die Identität, die es signiert hat.

    Seit #1915 laufen **beide** Prüfungen, als zwei Funktionen und nicht als eine. Die
    Herkunft steht zuerst, weil sie billig ist und den häufigeren Fall fängt (der
    öffentliche Build ist nicht gelaufen); die Signatur ist der kryptografische Beleg
    darüber. Geprüft wird gegen die **Identität des Arbeitsablaufs**, nicht gegen einen
    Schlüssel — es gibt keinen privaten Schlüssel, den jemand verlieren könnte.

    **Im Webdienst ist die Signaturprüfung aus.** Im Abbild liegt kein `cosign`; wäre sie
    dort Vorgabe, würde der Update-Knopf in jeder Installation mit einem Werkzeugfehler
    enden — ein Knopf, der nie funktioniert, ist schlechter als eine benannte Lücke. Auf
    der Befehlszeile ist sie Vorgabe und bricht ohne `cosign` ab; der Weg heraus
    (`--signatur aus`) ist eine ausdrückliche Entscheidung.

    Die Unterscheidung steht hier so deutlich, weil „signiert" und „geprüft" in
    Nachweisakten regelmäßig verwechselt werden.

## Was heute fehlt

Diese Punkte sind bekannt, erfasst und noch nicht geschlossen. Sie stehen hier, weil ein
Dossier, das nur das Erreichte nennt, als Nachweis wenig taugt.

| Punkt | Warum er zählt |
|---|---|
| **Keine Prüfsummen in der Abhängigkeitsliste** der Python-Pakete; es stehen Bereiche, keine festen Fassungen | Ein Baulauf kann eine andere Fassung ziehen als der vorige. Eine Sperrdatei mit Prüfsummen braucht ein Werkzeug, einen festen Platz im Bauprozess (`--require-hashes`) und einen dokumentierten Weg, sie bei jeder Änderung neu zu erzeugen — halb eingeführt wäre sie schlechter als gar nicht, weil der Bauprozess dann zwei Wahrheiten über die Abhängigkeiten hätte. Eigener Vorgang. |

Drei der vier Punkte, die diese Liste bis zum 2. November 2026 nannte, sind mit
#1915 geschlossen: die beweglichen Basis-Abbilder, der auf `pip` beschränkte
Dependabot und die fehlende Signaturprüfung im Deploy. Was bleibt, ist die
Sperrdatei mit Prüfsummen; sie wird als eigener Änderungsvorgang geführt und
nicht hier beschlossen.

## Verhältnis zu Art. 13 Abs. 6

Was zu tun ist, wenn **wir** eine Schwachstelle in einer Fremdkomponente finden, steht in
[Offenlegung und Austausch](schwachstellen-offenlegung.md). Dieses Dokument endet an der
Aufnahme und der Überwachung; die Meldung an den Hersteller ist ein eigener Vorgang.

**Fassung 1.0, 2. November 2026.** Fundstelle: Art. 13 Abs. 5 der Verordnung (EU)
2024/2847.
