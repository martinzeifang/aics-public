"""Fremdkomponenten in Klassen bewerten statt einzeln (#1773).

Eine echte SBOM dieser Anwendung führt 184 Komponenten. Beim Erst-Release gilt
jede als neu integriert, also verlangt der gerechnete Prüfpunkt
``fremdkomponenten_bewertet`` (Art. 13 Abs. 5) 184 begründete Einzelaussagen.
Fachlich ist das richtig. Praktisch ist es der Punkt, an dem jeder Anwender
alles markiert und einen Satz für alles schreibt — also genau die Umgehung, vor
der ``cra/release_checkliste.py`` im Dateikopf warnt. Ein Prüfpunkt, der nicht
bedienbar ist, wird nicht sorgfältiger beantwortet, sondern unaufrichtiger.

Die Sorgfaltspflicht ist aber nicht für jede Komponente dieselbe Frage. Ein
Paket des Basis-Images wird über die Distribution und den Image-Rebuild
versorgt; eine Python-Abhängigkeit der Anwendung über den Abhängigkeits-Scan
und einen Release. Diese Unterscheidung **steht in der SBOM** — im purl-Typ —
und wurde bisher nicht benutzt. Wer nach Klasse gruppiert, trifft deshalb nicht
weniger Entscheidungen als vorher; er trifft die, die tatsächlich verschieden
sind, und schreibt für gleichartige Fälle eine gemeinsame Begründung. Das ist
der Unterschied zwischen einer Sammelbegründung und einem Sammelhaken.

WAS HIER NICHT ERFUNDEN WIRD
„Direkte" gegen „transitive" Abhängigkeit wäre die Einteilung, die man sich
zuerst wünscht — und sie steht in einer SBOM ohne Abhängigkeitsgraph nicht
drin. Eine geratene Einordnung wäre in einer Nachweisakte schlechter als keine:
Sie liest sich wie eine Feststellung. Fehlt die purl, ist die Klasse
``unbestimmt``, und die Gruppe sagt das auch.

DER VORRANG, DER DAS GANZE TRÄGT
Eine Komponente mit **eigenem offenen Befund** (#1774) wandert in die Gruppe
``einzelpruefung`` und in keine Sammelbegründung. Sie ist nicht einer von
hundert gleichartigen Fällen, sondern ein eigener Sachverhalt — und eine
Gruppenbegründung, die ihn mitnimmt, wäre sachlich falsch für genau die
Komponente, auf die es ankommt.

ROLLE DER KI
Die KI schreibt den **Entwurf** der Begründung je Gruppe, aus den Daten der
Gruppe und den Nachweisen der Anwendung (Mechanismus #1483). Sie entscheidet
nichts: Status und Übernahme bleiben beim Menschen, und die Herkunft steht im
Register ``shared/ki_herkunft`` (#1765) — samt der Person, die den Entwurf
übernommen hat.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Ökosysteme, deren Pakete aus dem **Basis-Image** stammen. Sie werden nicht
#: von der Anwendung ausgewählt, sondern von der gewählten Distribution
#: mitgebracht — versorgt über deren Sicherheitsupdates und einen Rebuild.
OS_TYPEN = frozenset({"deb", "rpm", "apk", "alpm", "ebuild", "portage",
                      "nix", "swid"})

#: Das Image selbst (oder ein mitgeliefertes Image) — kein Paket, sondern der
#: Unterbau. Es trägt die Entscheidung, welche OS-Pakete überhaupt dabei sind.
IMAGE_TYPEN = frozenset({"oci", "docker"})

#: Ökosysteme der Anwendungsabhängigkeiten. Bewusst eine **Positivliste**:
#: Ein unbekannter purl-Typ soll nicht stillschweigend als
#: „Anwendungsabhängigkeit" durchlaufen, sondern als ``unbestimmt`` auffallen.
APP_TYPEN = frozenset({"pypi", "npm", "golang", "maven", "gradle", "cargo",
                       "gem", "nuget", "composer", "hex", "pub", "cran",
                       "cocoapods", "swift", "conan", "hackage", "luarocks",
                       "generic"})


@dataclass(frozen=True)
class Klasse:
    """Eine Komponentenklasse samt dem Sorgfaltsmaßstab, der für sie gilt.

    ``sorgfalt`` ist der Satz, der die Begründung trägt — er geht in den
    KI-Prompt und steht in der Oberfläche. Er beschreibt **was zu belegen ist**,
    nicht was belegt ist; das Zweite ist die Aussage des Anwenders.
    """
    key: str
    label: str
    beschreibung: str
    sorgfalt: str
    #: Darf für diese Klasse eine gemeinsame Begründung übernommen werden?
    sammel: bool = True


KLASSEN: tuple[Klasse, ...] = (
    Klasse(
        "einzelpruefung", "Einzelprüfung — eigener Befund vorhanden",
        "Gegen diese Komponenten steht mindestens ein offener Befund aus "
        "cra_vuln (Advisory, Dependabot, manuelle Erfassung oder Pentest).",
        "Hier ist je Komponente zu sagen, wie mit dem Befund umgegangen wird — "
        "behoben, in Behandlung, kompensiert oder begründet getragen. Eine "
        "Gruppenaussage über gleichartige Komponenten trifft diesen Fall nicht.",
        sammel=False),
    Klasse(
        "basisimage", "Basis-Image",
        "Das Container-Image, auf dem das Produkt aufsetzt (purl-Typ oci/docker).",
        "Zu belegen ist, welches Image in welchem Stand verwendet wird, wer es "
        "pflegt und wie ein neuer Stand in das Produkt kommt. Das Image "
        "entscheidet mittelbar über alle Betriebssystem-Pakete darin.",
        ),
    Klasse(
        "betriebssystem", "Betriebssystem-Paket",
        "Pakete der Distribution im Image (deb, rpm, apk …) — nicht von der "
        "Anwendung ausgewählt, sondern vom Basis-Image mitgebracht.",
        "Zu belegen ist, dass diese Pakete über die Sicherheitsupdates der "
        "Distribution versorgt werden und wie ein solcher Update-Stand ins "
        "Produkt gelangt (Image-Rebuild, Release). Eine Einzelbewertung je Paket "
        "wäre hier nicht aussagekräftiger: Der Versorgungsweg ist für alle "
        "derselbe.",
        ),
    Klasse(
        "anwendung", "Anwendungsabhängigkeit",
        "Pakete, die die Anwendung selbst einbindet (pypi, npm, maven …) — "
        "unabhängig davon, ob direkt oder über eine andere Abhängigkeit.",
        "Zu belegen ist, wie diese Abhängigkeiten auf bekannte Schwachstellen "
        "überwacht werden, in welcher Frist ein Befund zu einem Update führt "
        "und wer das entscheidet.",
        ),
    Klasse(
        "unbestimmt", "Herkunft unbestimmt",
        "Komponenten ohne purl oder mit unbekanntem Ökosystem — die SBOM sagt "
        "nicht, woher sie stammen.",
        "Zuerst ist die Herkunft zu klären: Ohne Ökosystem ist nicht bestimmbar, "
        "wie die Komponente auf Schwachstellen überwacht wird. Eine Bewertung, "
        "die darüber hinweggeht, behauptet eine Überwachung, die niemand "
        "benennen kann.",
        ),
)

_NACH_KEY = {k.key: k for k in KLASSEN}


def klasse(key: str) -> Klasse | None:
    return _NACH_KEY.get(str(key or ""))


def purl_typ(purl: Any) -> str:
    """Ökosystem aus einer purl lesen: ``pkg:pypi/flask@3.0`` → ``pypi``.

    Leer, wenn keine purl vorliegt oder sie nicht mit ``pkg:`` beginnt — der
    Fall landet dann in ``unbestimmt``, statt sich einen Typ zu geben.
    """
    s = str(purl or "").strip().lower()
    if not s.startswith("pkg:"):
        return ""
    rest = s[4:].lstrip("/")
    typ = rest.split("/", 1)[0].split("@", 1)[0].split("?", 1)[0]
    return typ.strip()


def klasse_fuer(komponente: dict[str, Any], *,
                hat_offenen_befund: bool = False) -> tuple[str, str]:
    """``(klasse, oekosystem)`` einer Komponente — deterministisch.

    Der offene Befund hat **Vorrang** vor allem anderen: Er macht aus einem
    gleichartigen Fall einen eigenen (#1774).

    Ohne purl entscheidet der Typ aus der SBOM, aber nur in zwei Fällen:
    ``operating-system`` und ``container`` sind eindeutig. Ein ``library`` ohne
    purl bleibt ``unbestimmt`` — die Klasse soll sagen, **wie** überwacht wird,
    und ohne Ökosystem ist das nicht zu sagen.
    """
    if hat_offenen_befund:
        return "einzelpruefung", ""
    typ = purl_typ(komponente.get("purl"))
    if typ in IMAGE_TYPEN:
        return "basisimage", typ
    if typ in OS_TYPEN:
        return "betriebssystem", typ
    if typ in APP_TYPEN:
        return "anwendung", typ
    sbom_typ = str(komponente.get("typ") or "").strip().lower()
    if sbom_typ == "operating-system":
        return "betriebssystem", ""
    if sbom_typ == "container":
        return "basisimage", ""
    return "unbestimmt", typ


def gruppen_key(klasse_key: str, oekosystem: str) -> str:
    """Stabiler Schlüssel einer Gruppe, wie ihn die Oberfläche zurückschickt."""
    return f"{klasse_key}:{oekosystem}" if oekosystem else klasse_key


def gruppiere(komponenten: list[dict[str, Any]], *,
              befunde: dict[str, list[dict[str, Any]]] | None = None,
              pflicht_keys: set[str] | frozenset[str] | None = None,
              nur_pflichtig: bool = False) -> list[dict[str, Any]]:
    """Komponenten zu Gruppen zusammenfassen (reine Funktion).

    ``pflicht_keys`` sind die nach Art. 13 Abs. 5 zu bewertenden Komponenten
    (neu aufgenommen oder angehoben, aus
    ``sbom_komponenten.befund``). Sie werden je Gruppe **gezählt**, damit
    sichtbar bleibt, wie viele Entscheidungen die Gruppe wirklich abnimmt;
    ``nur_pflichtig`` beschränkt die Gruppen darauf.

    Jede Gruppe nennt ``ids`` (die Komponenten, auf die eine Übernahme wirkt),
    ``offen`` (davon noch unbewertet), ``ohne_lizenz`` und bis zu zehn
    Beispielnamen. Die ``ids`` dienen der Anzeige — welche Komponenten eine
    Übernahme trifft, rechnet der Server beim Übernehmen erneut aus, damit eine
    veraltete Auswahl im Browser nicht die falschen Zeilen beschreibt.
    """
    bef = befunde or {}
    pflicht = set(pflicht_keys or ())
    roh: dict[str, dict[str, Any]] = {}

    for k in komponenten or []:
        key = str(k.get("komponent_key") or "")
        ist_pflichtig = (not pflicht) or (key in pflicht)
        if nur_pflichtig and pflicht and not ist_pflichtig:
            continue
        offener_befund = any(b.get("offen")
                             for b in (bef.get(key) or []))
        kl, oeko = klasse_fuer(k, hat_offenen_befund=offener_befund)
        gkey = gruppen_key(kl, oeko)
        g = roh.setdefault(gkey, {
            "key": gkey, "klasse": kl, "oekosystem": oeko,
            "ids": [], "anzahl": 0, "pflichtig": 0, "offen": 0,
            "bewertet": 0, "nicht_relevant": 0, "ohne_lizenz": 0,
            "mit_befund": 0, "lizenzen": set(), "beispiele": [],
        })
        g["ids"].append(int(k.get("id") or 0))
        g["anzahl"] += 1
        if ist_pflichtig:
            g["pflichtig"] += 1
        status = str(k.get("bewertung_status") or "offen")
        if status == "offen":
            g["offen"] += 1
        elif status == "nicht_relevant":
            g["nicht_relevant"] += 1
        else:
            g["bewertet"] += 1
        lizenz = str(k.get("lizenz") or "").strip()
        if lizenz:
            g["lizenzen"].add(lizenz)
        else:
            g["ohne_lizenz"] += 1
        if bef.get(key):
            g["mit_befund"] += 1
        if len(g["beispiele"]) < 10:
            g["beispiele"].append(
                f"{k.get('name') or key} {k.get('version') or ''}".strip())

    out: list[dict[str, Any]] = []
    for g in roh.values():
        kl = _NACH_KEY[g["klasse"]]
        lizenzen = sorted(g.pop("lizenzen"))
        out.append({
            **g,
            "label": kl.label + (f" · {g['oekosystem']}" if g["oekosystem"] else ""),
            "beschreibung": kl.beschreibung,
            "sorgfalt": kl.sorgfalt,
            "sammel": kl.sammel,
            "lizenzen": lizenzen[:12],
            "lizenzen_gesamt": len(lizenzen),
        })
    # Die Gruppe, die eine Einzelprüfung verlangt, steht oben — sie ist die
    # einzige, die Arbeit nicht abnimmt, sondern verlangt.
    rang = {k.key: i for i, k in enumerate(KLASSEN)}
    out.sort(key=lambda g: (rang.get(g["klasse"], 99), -g["anzahl"], g["key"]))
    return out


def ids_der_gruppe(komponenten: list[dict[str, Any]], gruppe_key: str, *,
                   befunde: dict[str, list[dict[str, Any]]] | None = None,
                   nur_offene: bool = False) -> list[int]:
    """IDs der Komponenten einer Gruppe — **serverseitig** neu bestimmt.

    Der Browser schickt den Gruppenschlüssel, nicht die Liste. Grund: Zwischen
    Anzeige und Übernahme kann ein Import gelaufen sein oder ein Befund
    eingetroffen; dann hätte eine mitgeschickte ID-Liste Komponenten getroffen,
    die inzwischen in die Einzelprüfung gehören. Eine Bewertung an der falschen
    Komponente ist in einer Nachweisakte ein stiller Fehler — er sieht aus wie
    eine Aussage.
    """
    bef = befunde or {}
    ids: list[int] = []
    for k in komponenten or []:
        key = str(k.get("komponent_key") or "")
        offener_befund = any(b.get("offen") for b in (bef.get(key) or []))
        kl, oeko = klasse_fuer(k, hat_offenen_befund=offener_befund)
        if gruppen_key(kl, oeko) != gruppe_key:
            continue
        if nur_offene and str(k.get("bewertung_status") or "offen") != "offen":
            continue
        ids.append(int(k.get("id") or 0))
    return [i for i in ids if i]


# ── Der Prompt für den Entwurf je Gruppe ─────────────────────────────────────

#: Was die KI liefern soll — und was nicht. Der Auftrag ist bewusst eng: Status
#: und Übernahme bleiben beim Menschen, und ein Entwurf, der eine Überwachung
#: behauptet, die es nicht gibt, wäre schlimmer als ein leeres Feld.
_AUFTRAG = """\
AUFTRAG
Formuliere **eine** Begründung für die oben genannte Gruppe, die als Bewertung
nach Art. 13 Abs. 5 CRA an jeder Komponente dieser Gruppe stehen kann.

Anforderungen an den Text:
* 3 bis 6 Sätze, sachlich, in der dritten Person, auf Deutsch.
* Er muss benennen: woher die Komponenten stammen, wie sie auf bekannte
  Schwachstellen überwacht werden und auf welchem Weg ein Update in das Produkt
  gelangt.
* Stütze dich **ausschließlich** auf die oben genannten Angaben. Ist ein Punkt
  dort nicht belegt, schreibe nicht, er sei erfüllt, sondern benenne ihn als
  noch zu belegen ("Der Überwachungsweg ist zu dokumentieren.").
* Keine Namen von Werkzeugen oder Diensten, die oben nicht vorkommen.
* Keine Aufzählung der einzelnen Komponenten, keine Anrede, keine Überschrift,
  keine Einleitung wie "Hier ist die Begründung".

Gib **nur** den Begründungstext zurück."""


def build_gruppen_prompt(projekt: dict[str, Any], version: str,
                         gruppe: dict[str, Any],
                         *, artefakt: str = "",
                         nachweise: list[str] | None = None) -> str:
    """Prompt für den Begründungs-Entwurf einer Gruppe.

    ``nachweise`` sind die Angaben aus der Anwendung, auf die der Text sich
    stützen darf (Schwachstellen-Sync, Update-Kanal, Support-Zeitraum …) —
    derselbe Gedanke wie die evidenzbewusste Bewertung aus #1483: Ein Modell,
    das den Zustand der Akte nicht kennt, erfindet ihn.
    """
    kl = _NACH_KEY.get(str(gruppe.get("klasse") or "")) or _NACH_KEY["unbestimmt"]
    zeilen: list[str] = [
        "Du unterstützt bei der CRA-Nachweisführung (Verordnung (EU) 2024/2847).",
        "Es geht um die Sorgfaltspflicht bei Komponenten Dritter, Art. 13 Abs. 5.",
        "",
        "## Produkt und Release",
        f"Produkt: {projekt.get('produkt') or projekt.get('name') or '—'}",
        f"Hersteller: {projekt.get('unternehmen') or '—'}",
        f"Release: {version or '—'}" + (f" · Artefakt: {artefakt}" if artefakt else ""),
        "",
        "## Gruppe",
        f"Klasse: {kl.label}",
        f"Was die Klasse umfasst: {kl.beschreibung}",
        f"Was zu belegen ist: {kl.sorgfalt}",
        f"Ökosystem: {gruppe.get('oekosystem') or 'nicht bestimmbar'}",
        f"Anzahl Komponenten in der Gruppe: {gruppe.get('anzahl') or 0}"
        f" (davon {gruppe.get('pflichtig') or 0} in diesem Release neu oder angehoben)",
    ]
    if gruppe.get("ohne_lizenz"):
        zeilen.append(f"Ohne Lizenzangabe in der SBOM: {gruppe['ohne_lizenz']}")
    if gruppe.get("lizenzen"):
        mehr = ("" if gruppe.get("lizenzen_gesamt", 0) <= len(gruppe["lizenzen"])
                else f" (von {gruppe['lizenzen_gesamt']} verschiedenen)")
        zeilen.append(f"Lizenzen: {', '.join(gruppe['lizenzen'])}{mehr}")
    if gruppe.get("beispiele"):
        zeilen.append(f"Beispiele: {', '.join(gruppe['beispiele'])}")
    if gruppe.get("mit_befund"):
        zeilen.append(
            f"Komponenten mit zugeordnetem Befund aus der Schwachstellenliste: "
            f"{gruppe['mit_befund']}")

    zeilen += ["", "## Nachweise aus der Anwendung"]
    if nachweise:
        zeilen += [f"* {n}" for n in nachweise]
    else:
        zeilen.append("* keine — zum Überwachungsweg liegt in der Akte nichts vor.")

    zeilen += ["", _AUFTRAG]
    return "\n".join(zeilen)


def nachweise_aus_projekt(sync_state: dict[str, Any] | None,
                          support: dict[str, Any] | None,
                          gruppe: dict[str, Any] | None = None,
                          *, repo: str = "") -> list[str]:
    """Belegbare Angaben für den Prompt — nur, was wirklich in der Akte steht.

    Jede Zeile ist eine Aussage, die in der Anwendung nachprüfbar ist. Fehlt
    eine Angabe, erscheint sie **nicht** als Platzhalter: Eine leere Zeile im
    Prompt lädt zum Ausfüllen ein, und ausgefüllt würde sie erfunden.

    ``repo`` kommt vom Aufrufer und nicht aus dem Projekt-Dict, weil die
    Repository-Angabe in ``meta_json`` unter mehreren Schlüsseln stehen kann
    (``cra/__init__._projekt_vcs``) — hier zu raten hieße, eine Zeile
    weglassen zu können, die vorhanden ist.
    """
    out: list[str] = []
    if str(repo or "").strip():
        out.append(f"Quellcode-Repository des Produkts: {repo}")
    if sync_state:
        quelle = str(sync_state.get("source") or "").strip()
        letzter = str(sync_state.get("last_sync_at") or "")[:19]
        if quelle or letzter:
            out.append(
                "Automatischer Abgleich der Schwachstellenlage ist eingerichtet"
                + (f" (Quelle: {quelle})" if quelle else "")
                + (f", letzter Lauf {letzter}" if letzter else "")
                + ".")
    if support:
        kanal = str(support.get("update_kanal") or "").strip()
        if kanal:
            out.append(f"Updates werden ausgeliefert über: {kanal}")
        jahre = support.get("support_jahre")
        if jahre:
            out.append(f"Zugesagter Support-Zeitraum: {jahre} Jahre")
        sic = support.get("sicherheitsupdate_kanal")
        if str(sic or "").strip():
            out.append(f"Kanal für Sicherheitsupdates: {sic}")
        if support.get("sicherheitsupdates_kostenlos"):
            out.append("Sicherheitsupdates sind kostenlos zugesagt.")
    if gruppe and gruppe.get("mit_befund"):
        out.append(
            f"{gruppe['mit_befund']} Komponente(n) dieser Gruppe sind in der "
            f"Schwachstellenliste des Projekts erfasst und werden dort behandelt.")
    return out


__all__ = ["KLASSEN", "Klasse", "OS_TYPEN", "IMAGE_TYPEN", "APP_TYPEN",
           "klasse", "purl_typ", "klasse_fuer", "gruppen_key", "gruppiere",
           "ids_der_gruppe", "build_gruppen_prompt", "nachweise_aus_projekt"]
