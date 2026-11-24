"""Verschlüsselung der Sicherungsarchive (#1916).

DER BEFUND
Eine Sicherung ist ein vollständiger Abzug des Datenbestands — alle Mandanten,
alle Nachweisdokumente, die Benutzertabelle, die Live-Konfiguration. Sie lag
unverschlüsselt im Dateisystem und ließ sich seit #1784 herunterladen. Bei
einem Werkzeug, das Nachweisakten für Dritte führt, ist das der schwerste
denkbare Vertraulichkeitsverlust (Anhang I Teil I Nr. 2 Buchst. e). Im
Abweichungsverzeichnis stand es als **B2**.

WARUM NICHT ``shared.crypto_at_rest.encrypt_bytes``
Das vorhandene Format ``AICSENC1`` ruft ``Fernet.encrypt(data)`` auf dem
**ganzen** Inhalt. Fernet hält Klartext und Chiffrat gleichzeitig im Speicher
und base64-kodiert das Ergebnis — ein Drittel mehr. Eine 144-MB-Sicherung wird
so zu rund 400 MB Spitzenverbrauch, und bei mehreren Gigabyte reißt es den
Worker. Für Datenbankfelder ist das Format richtig; für Archive nicht.

DIE ENTSCHEIDUNG, DIE HIER AM MEISTEN WIEGT
Ein verschlüsseltes Archiv, das nur diese Anwendung lesen kann, ist in zehn
Jahren **wertlos** — und zehn Jahre sind genau die Frist aus Art. 13 Abs. 13
(``docs/cra/aufbewahrung.md``, Festlegung 4: „prüfbar ohne die Anwendung").
Verschlüsselung und Aufbewahrungspflicht ziehen hier in verschiedene
Richtungen, und das Format löst den Widerspruch: Es ist **vollständig
dokumentiert** (unten und in der Beilegedatei neben jedem Archiv) und benutzt
ausschließlich Standardbausteine — PBKDF2-HMAC-SHA256 und AES-256-GCM. Wer in
zehn Jahren den Schlüssel hat, kann den Entschlüsseler in dreißig Zeilen
nachschreiben, auch ohne diesen Quellbaum.

DAS FORMAT ``AICSBAK1``

    Kopf (44 Byte, unverschlüsselt):
        0..7    MAGIC        b"AICSBAK1"
        8..23   salt         16 Byte, zufällig
        24..31  nonce_praefix 8 Byte, zufällig
        32..35  blockgroesse uint32, big-endian (Klartext je Block)
        36..39  iterationen  uint32, big-endian (PBKDF2)
        40..43  reserviert   uint32, big-endian, derzeit 0

    Schlüssel:
        key = PBKDF2-HMAC-SHA256(passphrase, salt, iterationen, 32 Byte)

    Danach Blöcke, bis zum Dateiende:
        4 Byte  laenge des Chiffrats (uint32, big-endian)
        n Byte  AES-256-GCM(nonce = nonce_praefix || index_be32,
                            aad   = MAGIC || index_be32 || b"\\x01" wenn letzter
                                    Block sonst b"\\x00",
                            tag angehängt, 16 Byte)

    Der **letzte** Block ist immer vorhanden und darf leer sein.

Die Blocknummer und das Letzter-Block-Kennzeichen stecken in den
authentifizierten Zusatzdaten. Das ist nicht Zierde: Ohne sie ließe sich ein
Archiv **abschneiden** oder Blöcke umordnen, und jeder einzelne Block bliebe
gültig. Ein Archiv, das sich unbemerkt kürzen lässt, ist als Nachweis nichts
wert.

DER SCHLÜSSEL HAT KEINEN RÜCKFALL
``AICS_BACKUP_KEY`` und sonst nichts. **Ausdrücklich kein Rückfall auf
``AICS_AT_REST_KEY`` oder ``JWT_SECRET_KEY``** — das ist genau die Kopplung
zweier Lebenszyklen, die als **B6** im Verzeichnis steht: Wer das
Sitzungsgeheimnis wechselt, macht sonst alle Sicherungen unlesbar, und zwar
lautlos. Ein Sicherungsschlüssel gehört außerdem *außerhalb* der Installation
verwahrt; einer, der aus ihr abgeleitet wird, liegt mit den Daten im selben
Korb.

Und: Ist die Verschlüsselung eingeschaltet und der Schlüssel fehlt, **scheitert
die Sicherung**. Sie darf nicht still im Klartext entstehen — ein
unverschlüsseltes Archiv, das für verschlüsselt gehalten wird, ist schlimmer
als ein offen unverschlüsseltes.
"""

from __future__ import annotations

import os
import secrets
import struct
from pathlib import Path
from typing import BinaryIO

MAGIC = b"AICSBAK1"
KOPF_LEN = 44
SALT_LEN = 16
NONCE_PRAEFIX_LEN = 8
TAG_LEN = 16

#: 4 MiB Klartext je Block. Groß genug, dass der Mehraufwand (4 Byte Länge +
#: 16 Byte Tag je Block) im Rauschen liegt — bei 1 GB sind es 5 kB —, und klein
#: genug, dass der Speicherbedarf nicht mit der Archivgröße wächst.
BLOCKGROESSE = 4 * 1024 * 1024

#: Wie ``shared.crypto_at_rest``. Ein abweichender Wert wäre eine zweite
#: Wahrheit über die Stärke der Ableitung; der Wert steht außerdem im Kopf,
#: damit ein künftig höherer Wert alte Archive nicht unlesbar macht.
ITERATIONEN = 200_000

#: Die **eine** Umgebungsvariable. Siehe Modul-Kopf: kein Rückfall.
SCHLUESSEL_ENV = "AICS_BACKUP_KEY"


class SchluesselFehlt(RuntimeError):
    """Verschlüsselung verlangt, Schlüssel nicht gesetzt — fail-closed."""


def schluessel_vorhanden() -> bool:
    return bool((os.environ.get(SCHLUESSEL_ENV) or "").strip())


def _passphrase() -> bytes:
    wert = (os.environ.get(SCHLUESSEL_ENV) or "").strip()
    if not wert:
        raise SchluesselFehlt(
            f"Die Verschlüsselung der Sicherungen ist eingeschaltet, aber "
            f"{SCHLUESSEL_ENV} ist nicht gesetzt. Die Sicherung wurde "
            f"abgebrochen — sie darf nicht still im Klartext entstehen. "
            f"Den Schlüssel in der Stack-Umgebung setzen und **außerhalb** der "
            f"Installation verwahren; ohne ihn ist kein Archiv mehr lesbar.")
    return wert.encode("utf-8")


def _ableiten(passphrase: bytes, salt: bytes, iterationen: int) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                      iterations=iterationen).derive(passphrase)


def _aad(index: int, letzter: bool) -> bytes:
    return MAGIC + struct.pack(">I", index) + (b"\x01" if letzter else b"\x00")


def ist_verschluesselt(pfad: Path) -> bool:
    """Trägt die Datei den Kopf des Archivformats?

    Billig und ohne Entschlüsselung — die Liste der Sicherungen braucht die
    Antwort für **jede** Datei und darf dafür keinen Schlüssel verlangen.
    """
    try:
        with open(pfad, "rb") as f:
            return f.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def verschluessele(quelle: Path, ziel: Path) -> dict[str, int]:
    """``quelle`` verschlüsselt nach ``ziel`` schreiben, blockweise."""
    schluessel = _ableiten(_passphrase(), salt := secrets.token_bytes(SALT_LEN),
                           ITERATIONEN)
    nonce_praefix = secrets.token_bytes(NONCE_PRAEFIX_LEN)
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aes = AESGCM(schluessel)
    gelesen = geschrieben = 0
    with open(quelle, "rb") as ein, open(ziel, "wb") as aus:
        aus.write(MAGIC + salt + nonce_praefix
                  + struct.pack(">III", BLOCKGROESSE, ITERATIONEN, 0))
        geschrieben += KOPF_LEN
        index = 0
        block = ein.read(BLOCKGROESSE)
        while True:
            naechster = ein.read(BLOCKGROESSE) if block else b""
            letzter = not naechster
            chiffrat = aes.encrypt(nonce_praefix + struct.pack(">I", index),
                                   block, _aad(index, letzter))
            aus.write(struct.pack(">I", len(chiffrat)) + chiffrat)
            gelesen += len(block)
            geschrieben += 4 + len(chiffrat)
            index += 1
            if letzter:
                break
            block = naechster
    return {"klartext_bytes": gelesen, "chiffrat_bytes": geschrieben,
            "bloecke": index}


def entschluessele(quelle: Path, ziel: Path) -> dict[str, int]:
    """Gegenstück. Wirft, wenn der Kopf fehlt, der Schlüssel falsch ist **oder
    das Archiv gekürzt wurde** — das Letzter-Block-Kennzeichen in den
    Zusatzdaten macht ein Abschneiden erkennbar."""
    with open(quelle, "rb") as ein, open(ziel, "wb") as aus:
        kopf = ein.read(KOPF_LEN)
        if len(kopf) != KOPF_LEN or not kopf.startswith(MAGIC):
            raise ValueError("Keine AICSBAK1-Datei (Kopf fehlt oder ist zu kurz).")
        salt = kopf[8:8 + SALT_LEN]
        nonce_praefix = kopf[8 + SALT_LEN:8 + SALT_LEN + NONCE_PRAEFIX_LEN]
        _blockgroesse, iterationen, _res = struct.unpack(">III", kopf[32:44])
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        aes = AESGCM(_ableiten(_passphrase(), salt, iterationen))
        index = 0
        geschrieben = 0
        while True:
            laenge_roh = ein.read(4)
            if len(laenge_roh) != 4:
                raise ValueError(
                    "Das Archiv endet vor dem letzten Block — es ist "
                    "unvollständig oder wurde gekürzt.")
            (laenge,) = struct.unpack(">I", laenge_roh)
            chiffrat = ein.read(laenge)
            if len(chiffrat) != laenge or laenge < TAG_LEN:
                raise ValueError("Block unvollständig — das Archiv ist beschädigt.")
            nonce = nonce_praefix + struct.pack(">I", index)
            # Erst als letzter Block versuchen; schlägt es fehl, ist es ein
            # mittlerer. Die Reihenfolge ist billiger als ein zweiter
            # Durchgang und hält die Prüfung auf Kürzung scharf.
            from cryptography.exceptions import InvalidTag
            try:
                klartext = aes.decrypt(nonce, chiffrat, _aad(index, True))
                letzter = True
            except InvalidTag:
                klartext = aes.decrypt(nonce, chiffrat, _aad(index, False))
                letzter = False
            aus.write(klartext)
            geschrieben += len(klartext)
            index += 1
            if letzter:
                break
    return {"klartext_bytes": geschrieben, "bloecke": index}


def beilege_text(archivname: str) -> str:
    """Die Beilegedatei neben dem Archiv — das Gegenstück zu Festlegung 4.

    Sie steht **unverschlüsselt** daneben und enthält keine Geheimnisse,
    sondern das Format. Wer in zehn Jahren das Archiv und den Schlüssel hat,
    aber diesen Quellbaum nicht, kommt damit an die Daten.
    """
    return f"""# Verschlüsseltes Sicherungsarchiv — {archivname}

Diese Datei liegt bewusst **im Klartext** neben dem Archiv. Sie enthält kein
Geheimnis, sondern die Beschreibung des Formats.

**Ohne den Schlüssel sind die Daten nicht wiederherstellbar.** Der Schlüssel
steht in der Umgebungsvariablen `{SCHLUESSEL_ENV}` der Installation und
gehört getrennt davon verwahrt. Er wird nicht mitgesichert.

## Format `AICSBAK1`

Kopf, {KOPF_LEN} Byte, unverschlüsselt:

| Bytes | Inhalt |
|---|---|
| 0–7 | `AICSBAK1` |
| 8–23 | Salt (16 Byte) |
| 24–31 | Nonce-Präfix (8 Byte) |
| 32–35 | Blockgröße, uint32 big-endian |
| 36–39 | PBKDF2-Iterationen, uint32 big-endian |
| 40–43 | reserviert, 0 |

Schlüsselableitung: `PBKDF2-HMAC-SHA256(Passphrase, Salt, Iterationen, 32 Byte)`.

Danach Blöcke bis zum Dateiende: 4 Byte Länge (uint32 big-endian), dann das
Chiffrat. Jeder Block ist `AES-256-GCM` mit

* Nonce = Nonce-Präfix ‖ Blocknummer (uint32 big-endian, ab 0)
* Zusatzdaten (AAD) = `AICSBAK1` ‖ Blocknummer ‖ `0x01` beim letzten Block,
  sonst `0x00`

Das Letzter-Block-Kennzeichen ist der Schutz gegen **Abschneiden**: Ohne es
bliebe ein gekürztes Archiv blockweise gültig.

## Entschlüsseln

Mit dieser Installation:

    python3 scripts/ops/backup_entschluesseln.py {archivname} ausgabe.zip

Ohne sie: Das Format oben lässt sich mit `cryptography` (Python) oder jeder
Bibliothek mit AES-GCM und PBKDF2 in wenigen Zeilen nachbauen. Das ist der
Zweck dieser Beilage — ein Archiv, das nur eine bestimmte Anwendung lesen
kann, taugt nicht für eine zehnjährige Aufbewahrungsfrist
(Art. 13 Abs. 13 der Verordnung (EU) 2024/2847).
"""
