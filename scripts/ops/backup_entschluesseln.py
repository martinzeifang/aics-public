#!/usr/bin/env python3
"""Ein verschlüsseltes Sicherungsarchiv entschlüsseln (#1916).

Dieses Skript ist der **Rückweg von außen**. Es läuft ohne die Anwendung, ohne
Datenbank und ohne Konfiguration — nur mit ``cryptography``. Das ist der Zweck:
Ein Archiv, das nur eine laufende Installation lesen kann, taugt nicht für die
zehnjährige Aufbewahrungsfrist aus Art. 13 Abs. 13 der Verordnung (EU)
2024/2847 (``docs/cra/aufbewahrung.md``, Festlegung 4).

    AICS_BACKUP_KEY='…' python3 scripts/ops/backup_entschluesseln.py \\
        out/backup/archiv_8.3.1_20261102_204500.zip ausgabe.zip

Das Format steht vollständig in ``shared/backup/verschluesselung.py`` und in
der Beilegedatei neben jedem Archiv. Wer in zehn Jahren weder dieses Skript
noch den Quellbaum hat, kann es daraus nachschreiben — die Bausteine sind
PBKDF2-HMAC-SHA256 und AES-256-GCM.

**Warum das Skript die Umgebungsvariable nimmt und keinen Parameter:** Ein
Schlüssel in der Befehlszeile steht in der Prozessliste und in der
Shell-Historie. Beides überlebt den Lauf.
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

MAGIC = b"AICSBAK1"
KOPF_LEN = 44
TAG_LEN = 16


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    quelle, ziel = Path(argv[1]), Path(argv[2])
    passphrase = (os.environ.get("AICS_BACKUP_KEY") or "").strip()
    if not passphrase:
        print("AICS_BACKUP_KEY ist nicht gesetzt.", file=sys.stderr)
        return 2
    if not quelle.is_file():
        print(f"{quelle} gibt es nicht.", file=sys.stderr)
        return 1
    if ziel.exists():
        print(f"{ziel} existiert bereits — nichts überschrieben.",
              file=sys.stderr)
        return 1

    # Ein Fehlversuch darf nichts zurücklassen. Die Zieldatei entsteht, bevor
    # der erste Block entschlüsselt ist, und der Riegel oben überschreibt
    # nichts Vorhandenes — eine vertippte Passphrase hätte den Rückweg damit
    # dauerhaft versperrt, und ein leeres Archiv neben dem verschlüsselten
    # sieht aus wie ein Ergebnis. Aufgefallen bei der Gegenprobe zu #1917.
    try:
        ergebnis = _entschluessele(quelle, ziel, passphrase)
    except BaseException:
        ziel.unlink(missing_ok=True)
        raise
    if ergebnis != 0:
        ziel.unlink(missing_ok=True)
    return ergebnis


def _entschluessele(quelle: Path, ziel: Path, passphrase: str) -> int:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    with open(quelle, "rb") as ein:
        kopf = ein.read(KOPF_LEN)
        if len(kopf) != KOPF_LEN or not kopf.startswith(MAGIC):
            print(f"{quelle} ist keine AICSBAK1-Datei.", file=sys.stderr)
            return 1
        salt, nonce_praefix = kopf[8:24], kopf[24:32]
        _blockgroesse, iterationen, _res = struct.unpack(">III", kopf[32:44])
        key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                         iterations=iterationen).derive(passphrase.encode("utf-8"))
        aes = AESGCM(key)

        with open(ziel, "wb") as aus:
            index = 0
            while True:
                roh = ein.read(4)
                if len(roh) != 4:
                    print("Das Archiv endet vor dem letzten Block — "
                          "unvollständig oder gekürzt.", file=sys.stderr)
                    return 1
                (laenge,) = struct.unpack(">I", roh)
                chiffrat = ein.read(laenge)
                if len(chiffrat) != laenge or laenge < TAG_LEN:
                    print("Block unvollständig — Archiv beschädigt.", file=sys.stderr)
                    return 1
                nonce = nonce_praefix + struct.pack(">I", index)
                kopfdaten = MAGIC + struct.pack(">I", index)
                try:
                    klartext = aes.decrypt(nonce, chiffrat, kopfdaten + b"\x01")
                    letzter = True
                except InvalidTag:
                    try:
                        klartext = aes.decrypt(nonce, chiffrat, kopfdaten + b"\x00")
                    except InvalidTag:
                        print("Entschlüsselung fehlgeschlagen — falscher "
                              "Schlüssel oder verändertes Archiv.", file=sys.stderr)
                        return 1
                    letzter = False
                aus.write(klartext)
                index += 1
                if letzter:
                    break
    print(f"{ziel} geschrieben ({index} Block/Blöcke, "
          f"{ziel.stat().st_size} Byte).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
