"""Vorgeschlagene Standardgruppen (#1780) — Vorschlag, nicht Vorbelegung.

Der Startzustand der Gruppenverwaltung ist leer, daneben stehen neunzehn Rollen,
und man soll raten, welche zusammengehören. Gruppen beim Start **automatisch
anzulegen** wäre aber die falsche Antwort: Eine Gruppe mit Rechten, die niemand
vergeben hat, ist eine stehende Rechtevergabe ohne Entscheider — in einem
Werkzeug, das Nachweisführung verkauft, die falsche Richtung. Dazu kennt eine
frische Installation den Zuschnitt des Hauses nicht (ein MSP mit dreihundert
Mandanten ist anders geschnitten als ein Hersteller mit einem Produkt), und eine
umbenannte oder gelöschte Seed-Gruppe käme beim nächsten Start wieder.

Deshalb ein Katalog, aus dem jemand auswählt. Angelegt wird nur das Angehakte,
und zwar über denselben Weg wie jede andere Gruppe.

WARUM DER KATALOG KURZ IST
Eine Gruppe mit genau **einer** Rolle bringt nichts — sie ist ein zweiter Name
für dieselbe Sache („SOC-Team" = ``soc_operator``). Aufgenommen ist nur, was
mehrere Rollen bündelt oder eine Arbeitsteilung abbildet, die man sonst jedes
Mal neu zusammensuchen müsste.

WAS HIER NICHT STEHT
Gruppen je Mandant. Das bräuchte ``allowed_firmen`` auf der Gruppe, also eine
Beschränkung, die sich schneiden müsste, während Rollen sich vereinigen — siehe
``server/auth/groups_db``. Ein eigener Schritt, kein Anhängsel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Vorschlag:
    """Eine vorgeschlagene Gruppe."""

    key: str
    name: str
    beschreibung: str
    roles: tuple[str, ...]
    extra_permissions: tuple[str, ...] = field(default=())


VORSCHLAEGE: tuple[Vorschlag, ...] = (
    Vorschlag(
        key="mandantenbetreuung",
        name="Mandantenbetreuung",
        beschreibung=(
            "Führt einen Mandanten fachlich über alle Module. Enthält über "
            "firmen:* auch die Pentest-Berichte. Ohne Freigaberechte und ohne "
            "Administration."),
        roles=("firmen_editor", "cra_editor", "nis2_editor", "aiact_editor",
               "dsgvo_editor", "wiba_editor", "risikobewertung_editor"),
    ),
    Vorschlag(
        key="produktteam",
        name="Produktteam / Entwicklung",
        beschreibung=(
            "Pflegt Anforderungen, SBOM, Schwachstellen und die Risikobewertung "
            "dahinter. Reicht Release-Vorgänge ein, gibt sie nicht frei."),
        roles=("cra_editor", "risikobewertung_editor"),
    ),
    Vorschlag(
        key="compliance_freigabe",
        name="Compliance-Freigabe",
        beschreibung=(
            "Die Gegenseite der Vier-Augen-Trennung: prüft und gibt frei — "
            "bewusst ohne Schreibrecht, denn ein Prüfer mit Schreibrecht kann "
            "den Gegenstand seiner Prüfung ändern."),
        roles=("cra_approver", "aiact_approver"),
    ),
    Vorschlag(
        key="geschaeftsfuehrung",
        name="Geschäftsführung",
        beschreibung=(
            "Liest überall mit und gibt den DSGVO-Jahresbericht frei "
            "(Art. 5 Abs. 2). Signiert wird von der/dem DSB."),
        roles=("geschaeftsfuehrer", "viewer"),
    ),
    Vorschlag(
        key="datenschutz",
        name="Datenschutz",
        beschreibung=(
            "DSB-Arbeit, wie sie tatsächlich anfällt: Die DSFA läuft über ein "
            "verknüpftes Risikobewertungs-Projekt, die TOM hängen an den "
            "WiBA-Prüffragen. Mit der DSB-Rolle allein kommt man an beidem "
            "nicht weiter."),
        roles=("dsb", "wiba_editor", "risikobewertung_editor"),
    ),
)


def katalog() -> list[dict[str, Any]]:
    """Die Vorschläge mit den Rechten, die sie tatsächlich ergeben.

    Die Zahl steht dabei, weil „cra_editor, risikobewertung_editor" nicht sagt,
    was jemand damit darf — und eine Gruppe anzulegen heißt, Rechte zu vergeben.
    """
    from server.models.permission import resolve_permissions

    out: list[dict[str, Any]] = []
    for v in VORSCHLAEGE:
        rechte = resolve_permissions(list(v.roles), list(v.extra_permissions))
        out.append({
            "key": v.key,
            "name": v.name,
            "beschreibung": v.beschreibung,
            "roles": list(v.roles),
            "extra_permissions": list(v.extra_permissions),
            "permissions": rechte,
            "permissions_count": len(rechte),
        })
    return out


def finde(key: str) -> Vorschlag | None:
    return next((v for v in VORSCHLAEGE if v.key == str(key or "")), None)
