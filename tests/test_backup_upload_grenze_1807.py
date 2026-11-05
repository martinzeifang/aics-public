"""Die eigene Sicherung muss sich zurückspielen lassen (#1807).

Aus dem Betrieb: „Wenn ich ein Backup aus dem Archiv hochladen will, kommt
*Fehler beim Upload*." Das Archiv war 56 MB groß.

Drei Schranken lagen hintereinander, und die großzügige war die letzte:

    nginx  client_max_body_size      50 MB   ← brach hier ab
    Flask  MAX_CONTENT_LENGTH (#743) 64 MB   ← hätte hier abgebrochen
    admin._upload_grenze()  (#1785)  4096 MB ← wurde nie erreicht

#1785 hob die Grenze in der Anwendung an und begründete das richtig — „eine
Grenze, die das Zurückspielen der eigenen Sicherung verhindert, ist keine
Schutzmaßnahme, sondern ein Ausfall". Nur stand genau diese Grenze danach
zweimal davor. Das fällt im Alltag nicht auf: Die Sicherung läuft, das Archiv
liegt da, und erst beim Wiederanlauf zeigt sich, dass es nicht zurückkommt.

Die Tests halten beide Richtungen fest: Der Backup-Upload ist ausgenommen —
und für jeden anderen Endpunkt bleibt die Schranke aus #743 wirksam.
"""
from __future__ import annotations

import re
from pathlib import Path

from flask import Flask, request

UPLOAD_PFAD = "/api/admin/backup/upload"


# ── Das Verfahren selbst: greift eine Grenze je Request? ─────────────────────

def test_pro_request_angehobene_grenze_greift():
    """Werkzeug lässt `request.max_content_length` je Request setzen.

    Ohne diesen Nachweis wäre der Fix eine Vermutung über die Bibliothek: Ein
    stillschweigend ignoriertes Attribut sähe im Code aus wie eine Lösung.
    """
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024  # 1 KB

    @app.before_request
    def _anheben():  # noqa: ANN202
        if request.path == "/gross":
            request.max_content_length = 10 * 1024 * 1024

    @app.post("/gross")
    def gross():  # noqa: ANN202
        return {"bytes": len(request.get_data())}

    @app.post("/klein")
    def klein():  # noqa: ANN202
        return {"bytes": len(request.get_data())}

    nutz = b"x" * (5 * 1024)
    with app.test_client() as c:
        assert c.post("/gross", data=nutz).status_code == 200
        assert c.post("/klein", data=nutz).status_code == 413, \
            "Die globale Grenze darf nur für den einen Pfad weichen"


# ── Die Verdrahtung in der Anwendung ─────────────────────────────────────────

def test_app_hebt_die_grenze_fuer_den_backup_upload_an():
    quelle = Path("server/app.py").read_text(encoding="utf-8")
    assert UPLOAD_PFAD in quelle, \
        "Der Backup-Upload ist nicht mehr von der globalen Grenze ausgenommen"
    assert "max_content_length" in quelle
    assert "_upload_grenze" in quelle, \
        "Die Ausnahme muss die Grenze der Route verwenden, nicht einen zweiten Wert"


def test_globale_grenze_bleibt_bestehen():
    """#743 wird nicht aufgeweicht — nur ein Pfad bekommt eine Ausnahme."""
    quelle = Path("server/app.py").read_text(encoding="utf-8")
    assert "MAX_CONTENT_LENGTH_MB" in quelle
    assert "app.config['MAX_CONTENT_LENGTH']" in quelle


# ── Die Schicht davor: nginx ─────────────────────────────────────────────────

def test_nginx_laesst_das_archiv_durch():
    """Die Anwendung sieht den Request sonst gar nicht erst.

    Der eigentliche Fehler lag hier: Die App-Grenze war längst 4 GB, aber nginx
    antwortete bei 50 MB mit 413 — für den Anwender „Fehler beim Upload", ohne
    dass in den Anwendungs-Logs etwas steht.
    """
    conf = Path("docker/nginx.conf").read_text(encoding="utf-8")

    m = re.search(r"location\s*=\s*" + re.escape(UPLOAD_PFAD) + r"\s*\{(.*?)\n        \}",
                  conf, re.S)
    assert m, f"Es gibt keinen eigenen location-Block für {UPLOAD_PFAD}"
    block = m.group(1)

    g = re.search(r"client_max_body_size\s+(\d+)([MG])", block)
    assert g, "Der Block setzt keine eigene client_max_body_size"
    mb = int(g.group(1)) * (1024 if g.group(2) == "G" else 1)
    assert mb >= 1024, f"{mb} MB sind zu wenig für eine gewachsene Sicherung"

    assert "proxy_pass" in block, "Der Block leitet nicht an die Anwendung weiter"


def test_globale_nginx_grenze_bleibt_klein():
    """Die Ausnahme gilt dem einen Pfad, nicht dem ganzen Server.

    Eine pauschal angehobene Grenze wäre die bequeme Lösung und würde jeden
    Endpunkt zur Ablagefläche machen.
    """
    conf = Path("docker/nginx.conf").read_text(encoding="utf-8")
    # Die globale Angabe steht im http-Block, vor der ersten `location`.
    global_teil = conf.split("location", 1)[0]
    g = re.search(r"client_max_body_size\s+(\d+)([MG])", global_teil)
    assert g, "Die globale Grenze ist verschwunden"
    mb = int(g.group(1)) * (1024 if g.group(2) == "G" else 1)
    assert mb <= 100, f"Die globale Grenze steht bei {mb} MB — das ist keine Ausnahme mehr"
