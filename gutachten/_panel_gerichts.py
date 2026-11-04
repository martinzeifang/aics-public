"""G8 — Desktop-Tk-Panel für BISG-Gerichtsgutachten + Privatgutachten.

Minimaler Workflow im Tk-Frontend:
- Liste der Verfahren
- Anlegen mit Toggle Gericht/Privat
- Editor für Stammdaten + Beweisfragen + Befunde + Beurteilungen + Assets
- DOCX-Export
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from gutachten import gerichts_db as _gdb
from gutachten import gerichtsgutachten_gen as _ggen
from gutachten import audit_to_pg as _a2pg
from gutachten import befangenheit as _befang
from gutachten import wizards as _wiz


class GerichtsgutachtenPanel(ttk.Frame):
    """Eigenständiges Tk-Panel für BISG-Gerichtsgutachten + Privatgutachten."""

    def __init__(self, parent, db_path: Path):
        super().__init__(parent)
        self._db = db_path
        self._aktuell: dict[str, Any] | None = None
        _gdb.ensure_db(db_path)
        self._build()
        self._refresh_liste()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Links: Liste
        left = ttk.Frame(self, padding=8)
        left.grid(row=0, column=0, sticky="nsw")
        ttk.Label(left, text="⚖ Gerichtsgutachten + 📋 Privatgutachten",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))

        self._lb = tk.Listbox(left, width=32, height=20, font=("Segoe UI", 10))
        self._lb.pack(fill="y", expand=False)
        self._lb.bind("<<ListboxSelect>>", self._on_select)

        btn_row = ttk.Frame(left)
        btn_row.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_row, text="+ Neu", command=self._open_new_dialog).pack(side="left", padx=2)
        ttk.Button(btn_row, text="🗑", command=self._delete_selected).pack(side="left", padx=2)
        ttk.Button(btn_row, text="↻", command=self._refresh_liste).pack(side="left", padx=2)

        # Phase H — Audit→PG Konversion (Desktop)
        h_row = ttk.Frame(left)
        h_row.pack(fill="x", pady=(4, 0))
        ttk.Button(h_row, text="📋 Audit → Privatgutachten",
                   command=self._open_audit_to_pg_wizard).pack(fill="x", padx=2)
        # Issue #703 — Workaround: Web-GUI öffnen für noch nicht portierte Features
        web_row = ttk.Frame(left)
        web_row.pack(fill="x", pady=(4, 0))
        ttk.Button(web_row, text="🌐 In Web-GUI öffnen (alle Features)",
                   command=self._open_in_web).pack(fill="x", padx=2)

        # Rechts: Editor
        right = ttk.Frame(self, padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self._title = ttk.Label(right, text="(kein Verfahren gewählt)",
                                font=("Segoe UI", 13, "bold"))
        self._title.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self._nb = ttk.Notebook(right)
        self._nb.grid(row=1, column=0, sticky="nsew")

        self._tab_stamm = ttk.Frame(self._nb, padding=10)
        self._tab_selbst = ttk.Frame(self._nb, padding=10)
        self._tab_bewf = ttk.Frame(self._nb, padding=10)
        self._tab_bef = ttk.Frame(self._nb, padding=10)
        self._tab_urt = ttk.Frame(self._nb, padding=10)
        self._tab_assets = ttk.Frame(self._nb, padding=10)
        self._tab_verf = ttk.Frame(self._nb, padding=10)
        self._nb.add(self._tab_stamm, text="Stammdaten")
        self._nb.add(self._tab_selbst, text="Selbstcheck (§ 406)")
        self._nb.add(self._tab_bewf, text="II. Beweisfragen")
        self._nb.add(self._tab_bef, text="IV. Befunde")
        self._nb.add(self._tab_urt, text="V. Beurteilungen")
        self._nb.add(self._tab_assets, text="Asservaten")
        self._nb.add(self._tab_verf, text="III. Verfahren")

        self._build_stamm_tab()
        self._build_selbst_tab()
        self._build_bewf_tab()
        self._build_bef_tab()
        self._build_urt_tab()
        self._build_assets_tab()
        self._build_verf_tab()

        # Unten: Export
        bottom = ttk.Frame(right, padding=4)
        bottom.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(bottom, text="📄 DOCX exportieren",
                   command=self._export_docx).pack(side="right", padx=2)
        ttk.Button(bottom, text="💾 Stammdaten speichern",
                   command=self._save_stammdaten).pack(side="right", padx=2)

    # ── Liste ────────────────────────────────────────────
    def _refresh_liste(self) -> None:
        self._lb.delete(0, "end")
        projekte = _gdb.list_gerichts_projekte(self._db)
        for p in projekte:
            self._lb.insert("end", f"{p['name']}  ({p.get('aktenzeichen', '—')})")
        self._projekte = projekte

    def _on_select(self, _evt=None) -> None:
        sel = self._lb.curselection()
        if not sel:
            return
        name = self._projekte[sel[0]]["name"]
        self._aktuell = _gdb.load_gerichts_projekt(self._db, name)
        if not self._aktuell:
            return
        is_privat = (self._aktuell.get("gutachten_art") or "gericht") == "privat"
        art = "📋 Privatgutachten" if is_privat else "⚖ Gerichtsgutachten"
        self._title.configure(text=f"{art}: {self._aktuell['name']}")
        self._load_stamm()
        self._refresh_bewf()
        self._refresh_bef()
        self._refresh_urt()
        self._refresh_assets()
        self._refresh_verf()

    # ── Neu-Anlegen Dialog ───────────────────────────────
    def _open_new_dialog(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("Neues Gutachten anlegen")
        dlg.geometry("520x520")
        dlg.transient(self.winfo_toplevel())

        art_var = tk.StringVar(value="gericht")
        fr = ttk.LabelFrame(dlg, text="Art", padding=10)
        fr.pack(fill="x", padx=10, pady=8)
        ttk.Radiobutton(fr, text="⚖ Gerichtsgutachten (gerichtsbestellt)",
                        variable=art_var, value="gericht",
                        command=lambda: self._toggle_dlg_fields(grid, art_var.get())).pack(anchor="w")
        ttk.Radiobutton(fr, text="📋 Privatgutachten (Mandanten-Auftrag)",
                        variable=art_var, value="privat",
                        command=lambda: self._toggle_dlg_fields(grid, art_var.get())).pack(anchor="w")

        grid = ttk.Frame(dlg, padding=10)
        grid.pack(fill="both", expand=True, padx=10)

        fields: dict[str, tk.StringVar] = {}

        def add(label: str, key: str, kind: str = "gemein") -> None:
            row = ttk.Frame(grid)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, width=22).pack(side="left")
            v = tk.StringVar()
            ttk.Entry(row, textvariable=v, width=40).pack(side="left", fill="x", expand=True)
            fields[key] = v
            row._kind = kind  # type: ignore[attr-defined]

        # Gemeinsam
        add("Projekt-Name *", "name")
        add("SV-Name *", "sv_name")
        add("Thema", "thema")
        # Gericht-spezifisch
        add("Gericht *", "gericht", kind="gericht")
        add("Aktenzeichen *", "aktenzeichen", kind="gericht")
        add("Kläger", "klaeger_name", kind="gericht")
        add("Beklagter", "beklagter_name", kind="gericht")
        # Privat-spezifisch
        add("Auftraggeber *", "auftraggeber", kind="privat")
        add("Auftrags-Art *", "auftrags_art", kind="privat")
        add("Auftrags-Nummer", "auftrags_nummer", kind="privat")
        add("Honorarvereinbarung", "honorarvereinbarung", kind="privat")

        self._toggle_dlg_fields(grid, "gericht")  # initial

        def do_create() -> None:
            data = {k: v.get().strip() for k, v in fields.items()}
            data["gutachten_art"] = art_var.get()
            if not data["name"] or not data["sv_name"]:
                messagebox.showerror("Fehler", "Projekt-Name + SV-Name sind Pflicht", parent=dlg)
                return
            if art_var.get() == "gericht" and (not data["gericht"] or not data["aktenzeichen"]):
                messagebox.showerror("Fehler", "Gericht + Aktenzeichen sind Pflicht", parent=dlg)
                return
            if art_var.get() == "privat" and (not data["auftraggeber"] or not data["auftrags_art"]):
                messagebox.showerror("Fehler", "Auftraggeber + Auftrags-Art sind Pflicht", parent=dlg)
                return
            try:
                _gdb.save_gerichts_projekt(self._db, **data)
                dlg.destroy()
                self._refresh_liste()
            except Exception as e:
                messagebox.showerror("Fehler", str(e), parent=dlg)

        btn_row = ttk.Frame(dlg, padding=10)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Abbrechen", command=dlg.destroy).pack(side="right", padx=4)
        ttk.Button(btn_row, text="Anlegen", command=do_create).pack(side="right")

    def _toggle_dlg_fields(self, grid: ttk.Frame, art: str) -> None:
        for child in grid.winfo_children():
            kind = getattr(child, "_kind", "gemein")
            if kind == "gemein" or kind == art:
                child.pack(fill="x", pady=2)
            else:
                child.pack_forget()

    def _delete_selected(self) -> None:
        if not self._aktuell:
            return
        if not messagebox.askyesno("Löschen", f"'{self._aktuell['name']}' wirklich löschen?"):
            return
        _gdb.delete_gerichts_projekt(self._db, self._aktuell["name"])
        self._aktuell = None
        self._refresh_liste()
        self._title.configure(text="(kein Verfahren gewählt)")

    # ── Stammdaten ────────────────────────────────────────
    def _build_stamm_tab(self) -> None:
        self._stamm_vars: dict[str, tk.StringVar] = {}
        row_idx = 0
        labels_gericht = [
            ("gericht", "Gericht"), ("kammer", "Kammer"), ("aktenzeichen", "Aktenzeichen"),
            ("beweisbeschluss_datum", "Beweisbeschluss vom"),
            ("klaeger_name", "Kläger"), ("beklagter_name", "Beklagter"),
        ]
        labels_privat = [
            ("auftraggeber", "Auftraggeber"), ("auftrags_art", "Auftrags-Art"),
            ("auftrags_datum", "Auftrags-Datum"), ("auftrags_nummer", "Auftrags-Nummer"),
            ("honorarvereinbarung", "Honorarvereinbarung"),
        ]
        labels_gemein = [
            ("thema", "Thema"), ("sv_name", "SV-Name"),
            ("sv_zertifizierung", "SV-Zertifizierung"),
            ("sv_anschrift", "SV-Anschrift"), ("sv_kontakt", "SV-Kontakt"),
        ]
        for key, label in labels_gericht + labels_privat + labels_gemein:
            ttk.Label(self._tab_stamm, text=label).grid(row=row_idx, column=0, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            ttk.Entry(self._tab_stamm, textvariable=v, width=60).grid(
                row=row_idx, column=1, sticky="ew", padx=4, pady=2)
            self._stamm_vars[key] = v
            row_idx += 1
        self._tab_stamm.columnconfigure(1, weight=1)

    def _load_stamm(self) -> None:
        if not self._aktuell:
            return
        for k, v in self._stamm_vars.items():
            v.set(str(self._aktuell.get(k, "")))

    def _save_stammdaten(self) -> None:
        if not self._aktuell:
            return
        data = {k: v.get() for k, v in self._stamm_vars.items()}
        data["name"] = self._aktuell["name"]
        data["gutachten_art"] = self._aktuell.get("gutachten_art", "gericht")
        try:
            _gdb.save_gerichts_projekt(self._db, **data)
            self._aktuell = _gdb.load_gerichts_projekt(self._db, data["name"])
            messagebox.showinfo("OK", "Stammdaten gespeichert.")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    # ── Beweisfragen Tab ──────────────────────────────────
    def _build_bewf_tab(self) -> None:
        cols = ("nr", "frage_text", "antwort_kurz", "antwort_text")
        self._tree_bewf = ttk.Treeview(self._tab_bewf, columns=cols, show="headings", height=10)
        for c, label, w in [("nr", "Nr", 50), ("frage_text", "Frage", 400),
                            ("antwort_kurz", "Antw.", 80), ("antwort_text", "Antwort", 300)]:
            self._tree_bewf.heading(c, text=label)
            self._tree_bewf.column(c, width=w, anchor="w")
        self._tree_bewf.pack(fill="both", expand=True)

        add = ttk.Frame(self._tab_bewf)
        add.pack(fill="x", pady=4)
        ttk.Label(add, text="Nr:").pack(side="left")
        self._bewf_nr = tk.IntVar(value=1)
        ttk.Entry(add, textvariable=self._bewf_nr, width=5).pack(side="left", padx=2)
        ttk.Label(add, text="Frage:").pack(side="left")
        self._bewf_frage = tk.StringVar()
        ttk.Entry(add, textvariable=self._bewf_frage, width=40).pack(side="left", padx=2)
        ttk.Button(add, text="+ Hinzu", command=self._add_bewf).pack(side="left", padx=4)
        ttk.Button(add, text="🗑", command=self._del_bewf).pack(side="left", padx=2)

    def _refresh_bewf(self) -> None:
        for i in self._tree_bewf.get_children():
            self._tree_bewf.delete(i)
        if not self._aktuell:
            return
        for f in _gdb.list_beweisfragen(self._db, self._aktuell["name"]):
            self._tree_bewf.insert("", "end", iid=str(f["id"]),
                                   values=(f["nr"], f["frage_text"], f["antwort_kurz"], f["antwort_text"]))

    def _add_bewf(self) -> None:
        if not self._aktuell:
            return
        _gdb.save_beweisfrage(self._db, projekt_name=self._aktuell["name"],
                              nr=int(self._bewf_nr.get()), frage_text=self._bewf_frage.get())
        self._bewf_nr.set(int(self._bewf_nr.get()) + 1)
        self._bewf_frage.set("")
        self._refresh_bewf()

    def _del_bewf(self) -> None:
        sel = self._tree_bewf.selection()
        if not sel:
            return
        _gdb.delete_beweisfrage(self._db, int(sel[0]))
        self._refresh_bewf()

    # ── Befunde Tab ───────────────────────────────────────
    def _build_bef_tab(self) -> None:
        cols = ("nr", "titel", "methode", "werkzeug")
        self._tree_bef = ttk.Treeview(self._tab_bef, columns=cols, show="headings", height=10)
        for c, label, w in [("nr", "Nr", 60), ("titel", "Titel", 350),
                            ("methode", "Methode", 100), ("werkzeug", "Werkzeug", 150)]:
            self._tree_bef.heading(c, text=label)
            self._tree_bef.column(c, width=w, anchor="w")
        self._tree_bef.pack(fill="both", expand=True)

        add = ttk.Frame(self._tab_bef)
        add.pack(fill="x", pady=4)
        ttk.Label(add, text="Nr:").pack(side="left")
        self._bef_nr = tk.StringVar(value="4.1")
        ttk.Entry(add, textvariable=self._bef_nr, width=8).pack(side="left", padx=2)
        ttk.Label(add, text="Titel:").pack(side="left")
        self._bef_titel = tk.StringVar()
        ttk.Entry(add, textvariable=self._bef_titel, width=40).pack(side="left", padx=2)
        ttk.Button(add, text="+ Hinzu", command=self._add_bef).pack(side="left", padx=4)
        ttk.Button(add, text="🗑", command=self._del_bef).pack(side="left", padx=2)

    def _refresh_bef(self) -> None:
        for i in self._tree_bef.get_children():
            self._tree_bef.delete(i)
        if not self._aktuell:
            return
        for b in _gdb.list_befunde(self._db, self._aktuell["name"]):
            self._tree_bef.insert("", "end", iid=str(b["id"]),
                                  values=(b["nr"], b["titel"], b["methode"],
                                          f"{b['werkzeug_name']} {b['werkzeug_version']}"))

    def _add_bef(self) -> None:
        if not self._aktuell:
            return
        _gdb.save_befund(self._db, projekt_name=self._aktuell["name"],
                         nr=self._bef_nr.get(), titel=self._bef_titel.get())
        self._bef_titel.set("")
        self._refresh_bef()

    def _del_bef(self) -> None:
        sel = self._tree_bef.selection()
        if not sel:
            return
        _gdb.delete_befund(self._db, int(sel[0]))
        self._refresh_bef()

    # ── Beurteilungen Tab ─────────────────────────────────
    def _build_urt_tab(self) -> None:
        cols = ("nr", "titel", "norm_referenz")
        self._tree_urt = ttk.Treeview(self._tab_urt, columns=cols, show="headings", height=10)
        for c, label, w in [("nr", "Nr", 60), ("titel", "Titel", 300), ("norm_referenz", "Norm", 350)]:
            self._tree_urt.heading(c, text=label)
            self._tree_urt.column(c, width=w, anchor="w")
        self._tree_urt.pack(fill="both", expand=True)

        add = ttk.Frame(self._tab_urt)
        add.pack(fill="x", pady=4)
        ttk.Label(add, text="Nr:").pack(side="left")
        self._urt_nr = tk.StringVar(value="5.1")
        ttk.Entry(add, textvariable=self._urt_nr, width=8).pack(side="left", padx=2)
        ttk.Label(add, text="Titel:").pack(side="left")
        self._urt_titel = tk.StringVar()
        ttk.Entry(add, textvariable=self._urt_titel, width=20).pack(side="left", padx=2)
        ttk.Label(add, text="Norm:").pack(side="left")
        self._urt_norm = tk.StringVar()
        ttk.Entry(add, textvariable=self._urt_norm, width=25).pack(side="left", padx=2)
        ttk.Button(add, text="+ Hinzu", command=self._add_urt).pack(side="left", padx=4)
        ttk.Button(add, text="🗑", command=self._del_urt).pack(side="left", padx=2)

    def _refresh_urt(self) -> None:
        for i in self._tree_urt.get_children():
            self._tree_urt.delete(i)
        if not self._aktuell:
            return
        for u in _gdb.list_beurteilungen(self._db, self._aktuell["name"]):
            self._tree_urt.insert("", "end", iid=str(u["id"]),
                                  values=(u["nr"], u["titel"], u["norm_referenz"]))

    def _add_urt(self) -> None:
        if not self._aktuell:
            return
        _gdb.save_beurteilung(self._db, projekt_name=self._aktuell["name"],
                              nr=self._urt_nr.get(), titel=self._urt_titel.get(),
                              norm_referenz=self._urt_norm.get(), befund_ids=[])
        self._urt_titel.set(""); self._urt_norm.set("")
        self._refresh_urt()

    def _del_urt(self) -> None:
        sel = self._tree_urt.selection()
        if not sel:
            return
        _gdb.delete_beurteilung(self._db, int(sel[0]))
        self._refresh_urt()

    # ── Assets Tab ────────────────────────────────────────
    def _build_assets_tab(self) -> None:
        cols = ("bez", "sha", "werkzeug")
        self._tree_assets = ttk.Treeview(self._tab_assets, columns=cols, show="headings", height=10)
        for c, label, w in [("bez", "Bezeichnung", 250), ("sha", "SHA-256", 200),
                            ("werkzeug", "Werkzeug", 200)]:
            self._tree_assets.heading(c, text=label)
            self._tree_assets.column(c, width=w, anchor="w")
        self._tree_assets.pack(fill="both", expand=True)

        ttk.Button(self._tab_assets, text="📁 Datei sichern (SHA-256 berechnen + speichern)",
                   command=self._upload_asset).pack(pady=8)

    def _refresh_assets(self) -> None:
        for i in self._tree_assets.get_children():
            self._tree_assets.delete(i)
        if not self._aktuell:
            return
        for a in _gdb.list_assets(self._db, self._aktuell["name"]):
            self._tree_assets.insert("", "end", iid=str(a["id"]),
                                     values=(a["bezeichnung"], (a["sha256"] or "")[:32] + "…",
                                             f"{a['werkzeug_name']} {a['werkzeug_version']}"))

    def _upload_asset(self) -> None:
        if not self._aktuell:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Verfahren auswählen.")
            return
        path = filedialog.askopenfilename(title="Asservat auswählen")
        if not path:
            return
        with open(path, "rb") as f:
            data = f.read()
        sha = _gdb.compute_sha256(data)
        bez = Path(path).name
        from datetime import datetime, timezone
        _gdb.save_asset(self._db, projekt_name=self._aktuell["name"], bezeichnung=bez,
                        sha256=sha, original_dateiname=bez,
                        akquisitions_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        self._refresh_assets()
        messagebox.showinfo("Asservat gespeichert", f"{bez}\nSHA-256: {sha[:32]}…")

    # ── Export ───────────────────────────────────────────
    def _export_docx(self) -> None:
        if not self._aktuell:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Verfahren auswählen.")
            return
        try:
            doc = _ggen.build_gerichtsgutachten_docx(self._aktuell["name"], self._db)
        except ValueError as e:
            messagebox.showerror("Validierungs-Fehler", str(e))
            return
        path = filedialog.asksaveasfilename(
            title="DOCX speichern",
            defaultextension=".docx",
            initialfile=f"Gutachten_{self._aktuell['name']}.docx",
            filetypes=[("Word", "*.docx")],
        )
        if not path:
            return
        doc.save(path)
        messagebox.showinfo("Export OK", f"Gespeichert: {path}")

    # ──────────────────────────────────────────────────────
    # Issue #703 — Desktop-Web-Parity: Selbstcheck-Tab (P0)
    # ──────────────────────────────────────────────────────
    def _build_selbst_tab(self) -> None:
        intro = ttk.Label(
            self._tab_selbst,
            text=("G2-1 — Befangenheits-Selbstcheck (§ 406 ZPO)\n"
                  "Beantworte alle Fragen wahrheitsgemäß. Bei 'ja' bei Kompetenz → ablehnen."),
            font=("Segoe UI", 10), justify="left",
        )
        intro.pack(anchor="w", pady=(0, 8))

        self._selbst_vars: dict[str, tk.StringVar] = {}
        for f in _wiz.SELBSTCHECK_FRAGEN:
            row = ttk.LabelFrame(self._tab_selbst, text=f["frage"], padding=6)
            row.pack(fill="x", pady=4)
            v = tk.StringVar(value="")
            self._selbst_vars[f["key"]] = v
            inner = ttk.Frame(row)
            inner.pack(anchor="w")
            ttk.Radiobutton(inner, text="Ja", variable=v, value="ja").pack(side="left", padx=4)
            ttk.Radiobutton(inner, text="Nein", variable=v, value="nein").pack(side="left", padx=4)
            ttk.Radiobutton(inner, text="Unklar", variable=v, value="unklar").pack(side="left", padx=4)

        btn_row = ttk.Frame(self._tab_selbst)
        btn_row.pack(fill="x", pady=(8, 4))
        ttk.Button(btn_row, text="🔍 Auswerten", command=self._run_selbstcheck).pack(side="left")

        # Ergebnis-Anzeige
        self._selbst_result = tk.Text(self._tab_selbst, height=8, wrap="word")
        self._selbst_result.pack(fill="both", expand=True, pady=(8, 4))

        # Fließtext-Editor
        ttk.Label(self._tab_selbst, text="Befangenheits-Fließtext (geht in DOCX Kap. III):",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 2))
        self._selbst_fliesstext = tk.Text(self._tab_selbst, height=10, wrap="word")
        self._selbst_fliesstext.pack(fill="both", expand=True)

        f_row = ttk.Frame(self._tab_selbst)
        f_row.pack(fill="x", pady=(4, 0))
        ttk.Button(f_row, text="💾 Fließtext speichern",
                   command=self._save_fliesstext).pack(side="right")

    def _run_selbstcheck(self) -> None:
        if not self._aktuell:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Verfahren auswählen.")
            return
        antw = {k: v.get() for k, v in self._selbst_vars.items()}
        try:
            r = _wiz.selbstcheck(self._db, self._aktuell["name"], antw,
                                 sv_user=self._aktuell.get("sv_name", ""))
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
            return
        self._selbst_result.delete("1.0", "end")
        self._selbst_result.insert("1.0", f"Status: {r.get('status', '?').upper()}\n")
        emp = r.get("empfehlung", {})
        self._selbst_result.insert("end", f"\n{emp.get('headline', '')}\n{emp.get('empfehlung', '')}\n")
        for i in r.get("issues", []):
            self._selbst_result.insert("end", f"\n• [{i['level']}] {i['message']}")
        self._selbst_fliesstext.delete("1.0", "end")
        self._selbst_fliesstext.insert("1.0", r.get("fliesstext", ""))
        self._refresh_verf()  # Verfahrensgang aktualisieren

    def _save_fliesstext(self) -> None:
        """Aktualisiert den jüngsten Selbstcheck-Eintrag mit editiertem Fließtext."""
        if not self._aktuell:
            return
        text = self._selbst_fliesstext.get("1.0", "end").strip()
        if not text:
            return
        # Letzten Selbstcheck finden + überschreiben
        events = _gdb.list_verfahrensereignisse(self._db, self._aktuell["name"])
        sc = [e for e in events if e.get("ereignis_typ") == "selbstcheck"]
        if not sc:
            messagebox.showinfo("Kein Selbstcheck", "Bitte erst Auswerten klicken.")
            return
        last = sc[-1]
        _gdb.save_verfahrensereignis(
            self._db, id=last["id"], projekt_name=self._aktuell["name"],
            ereignis_typ="selbstcheck", titel=last.get("titel", ""),
            beschreibung=text, empfaenger=last.get("empfaenger", []),
        )
        messagebox.showinfo("OK", "Fließtext gespeichert.")
        self._refresh_verf()

    # ──────────────────────────────────────────────────────
    # Issue #703 — Desktop-Web-Parity: Verfahrensgang (P0)
    # ──────────────────────────────────────────────────────
    def _build_verf_tab(self) -> None:
        cols = ("datum", "typ", "titel")
        self._tree_verf = ttk.Treeview(self._tab_verf, columns=cols, show="headings", height=12)
        for c, lbl, w in [("datum", "Datum", 110), ("typ", "Typ", 130),
                          ("titel", "Titel", 460)]:
            self._tree_verf.heading(c, text=lbl)
            self._tree_verf.column(c, width=w, anchor="w")
        self._tree_verf.pack(fill="both", expand=True)
        self._tree_verf.bind("<<TreeviewSelect>>", self._on_verf_select)

        # Detail-Bereich
        det_frame = ttk.LabelFrame(self._tab_verf, text="Details", padding=6)
        det_frame.pack(fill="both", expand=False, pady=(6, 0))
        self._verf_detail = tk.Text(det_frame, height=8, wrap="word")
        self._verf_detail.pack(fill="both", expand=True)

        add = ttk.Frame(self._tab_verf)
        add.pack(fill="x", pady=6)
        ttk.Label(add, text="Typ:").pack(side="left")
        self._verf_typ = tk.StringVar(value="akteneinsicht")
        ttk.Combobox(add, textvariable=self._verf_typ, width=22,
                     values=["akteneinsicht", "parteikommunikation", "ortstermin",
                             "asservat-aufnahme", "labor-analyse", "gutachten-versand",
                             "selbstcheck", "befangenheitspruefung", "sonstiges"],
                     state="readonly").pack(side="left", padx=2)
        ttk.Label(add, text="Titel:").pack(side="left")
        self._verf_titel = tk.StringVar()
        ttk.Entry(add, textvariable=self._verf_titel, width=40).pack(side="left", padx=2)
        ttk.Button(add, text="+ Hinzu", command=self._add_verf).pack(side="left", padx=4)
        ttk.Button(add, text="🗑", command=self._del_verf).pack(side="left", padx=2)

    def _refresh_verf(self) -> None:
        if not hasattr(self, "_tree_verf"):
            return
        for i in self._tree_verf.get_children():
            self._tree_verf.delete(i)
        if not self._aktuell:
            return
        for e in _gdb.list_verfahrensereignisse(self._db, self._aktuell["name"]):
            self._tree_verf.insert("", "end", iid=str(e["id"]),
                                   values=((e.get("ereignis_datum") or "")[:10],
                                           e.get("ereignis_typ", ""), e.get("titel", "")))

    def _on_verf_select(self, _evt=None) -> None:
        sel = self._tree_verf.selection()
        if not sel:
            return
        events = _gdb.list_verfahrensereignisse(self._db, self._aktuell["name"])
        ev = next((e for e in events if str(e["id"]) == sel[0]), None)
        if not ev:
            return
        self._verf_detail.delete("1.0", "end")
        self._verf_detail.insert("1.0", ev.get("beschreibung", ""))

    def _add_verf(self) -> None:
        if not self._aktuell:
            return
        _gdb.save_verfahrensereignis(
            self._db, projekt_name=self._aktuell["name"],
            ereignis_typ=self._verf_typ.get(), titel=self._verf_titel.get(),
            beschreibung="", empfaenger=[],
        )
        self._verf_titel.set("")
        self._refresh_verf()

    def _del_verf(self) -> None:
        sel = self._tree_verf.selection()
        if not sel:
            return
        _gdb.delete_verfahrensereignis(self._db, int(sel[0]))
        self._refresh_verf()

    # ──────────────────────────────────────────────────────
    # Issue #703 — "In Web-GUI öffnen"
    # ──────────────────────────────────────────────────────
    def _open_in_web(self) -> None:
        """Öffnet die Web-GUI im Standard-Browser. Web/Desktop teilen die SQLite-DB."""
        import webbrowser
        url = "https://localhost:8443/#/gutachten/gerichts"
        if self._aktuell:
            url += f"?projekt={self._aktuell['name']}"
        if not messagebox.askyesno(
            "Web-GUI öffnen",
            f"Die Web-GUI bietet alle Features (Selbstcheck, Forensik, Honorar,\n"
            f"Hypothesen, Peer-Review, etc.).\n\n"
            f"Web- und Desktop-GUI teilen sich dieselbe Datenbank.\n\n"
            f"Browser-URL öffnen?\n{url}",
        ):
            return
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Fehler", f"Browser konnte nicht geöffnet werden: {e}")

    # ──────────────────────────────────────────────────────
    # Phase H — Desktop-Wizard Audit → PG (Issues #680-#689)
    # ──────────────────────────────────────────────────────

    def _open_audit_to_pg_wizard(self) -> None:
        """4-Step-Wizard: Audit-Bericht in Privatgutachten überführen."""
        # Audit-DB: gleiche gutachten.sqlite (Audit-Berichte + PGs gemeinsam)
        audit_db = self._db
        audit_projekte = _a2pg.list_audit_projekte(audit_db)
        if not audit_projekte:
            messagebox.showinfo("Keine Audit-Berichte",
                                "Es sind keine Compliance-Audit-Berichte vorhanden.\n"
                                "Lege erst einen Audit-Bericht im Gutachten-Modul an.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("📋 Audit-Bericht → Privatgutachten (Wizard)")
        dlg.geometry("720x640")
        dlg.transient(self.winfo_toplevel())

        state = {
            "step": 1,
            "audit_name": "",
            "summary": None,
            "warning": None,
            "gaps": [],
            "selected_gaps": set(),
            "acceptance": tk.BooleanVar(value=False),
            "einheitlich": tk.BooleanVar(value=False),  # #705: Audit ist Teil des Gutachtens
            "pg_name": tk.StringVar(),
            "sv_name": tk.StringVar(),
            "auftrags_art": tk.StringVar(value="Tauglichkeitsprüfung"),
            "auftrags_datum": tk.StringVar(),
            "auftrags_nummer": tk.StringVar(),
            "thema": tk.StringVar(),
            "honorar": tk.StringVar(),
            "result": None,
        }
        from datetime import datetime as _dt
        state["auftrags_datum"].set(_dt.now().strftime("%Y-%m-%d"))

        # Step-Container (wird neu aufgebaut)
        container = ttk.Frame(dlg, padding=10)
        container.pack(fill="both", expand=True)

        # Footer mit Navigation
        footer = ttk.Frame(dlg, padding=8)
        footer.pack(fill="x")
        title_lbl = ttk.Label(dlg, text="", font=("Segoe UI", 12, "bold"))
        title_lbl.pack(before=container, anchor="w", padx=10, pady=(8, 4))

        btn_back = ttk.Button(footer, text="⟵ Zurück")
        btn_back.pack(side="left", padx=4)
        btn_next = ttk.Button(footer, text="Weiter ⟶")
        btn_next.pack(side="right", padx=4)
        btn_cancel = ttk.Button(footer, text="Abbrechen", command=dlg.destroy)
        btn_cancel.pack(side="right", padx=4)

        def render() -> None:
            for c in container.winfo_children():
                c.destroy()
            title_lbl.configure(text=f"Schritt {state['step']}/4 — "
                                + ["", "Audit-Auswahl + Vorbefassungs-Hinweis",
                                   "PG-Stammdaten", "Befund-Kandidaten (§ 407a)",
                                   "Zusammenfassung & Konvertierung"][state["step"]])
            if state["step"] == 1:
                self._wizard_step1(container, state, audit_projekte, audit_db)
            elif state["step"] == 2:
                self._wizard_step2(container, state)
            elif state["step"] == 3:
                self._wizard_step3(container, state)
            elif state["step"] == 4:
                self._wizard_step4(container, state, audit_db, dlg)

            btn_back.configure(state="normal" if state["step"] > 1 else "disabled")
            btn_next.configure(
                text="✅ Anlegen" if state["step"] == 4 else "Weiter ⟶",
                command=(lambda: self._wizard_execute(state, audit_db, dlg, render))
                       if state["step"] == 4
                       else (lambda: _advance()),
            )

        def _advance() -> None:
            if state["step"] == 1:
                # #705: Akzeptanz nur nötig, wenn Audit eine separate Vorbefassung ist
                if not state["einheitlich"].get() and not state["acceptance"].get():
                    messagebox.showwarning(
                        "Akzeptanz erforderlich",
                        "Bitte den Vorbefassungs-Hinweis akzeptieren, um fortzufahren.\n"
                        "(Oder wählen Sie 'Audit ist Teil des Gutachtens'.)",
                        parent=dlg,
                    )
                    return
            if state["step"] == 2:
                if not state["pg_name"].get().strip() or not state["sv_name"].get().strip():
                    messagebox.showwarning("Pflichtfelder", "PG-Name + SV-Name sind Pflicht.", parent=dlg)
                    return
            state["step"] += 1
            render()

        def _back() -> None:
            if state["step"] > 1:
                state["step"] -= 1
                render()

        btn_back.configure(command=_back)
        render()

    def _wizard_step1(self, parent, state, audit_projekte, audit_db) -> None:
        ttk.Label(parent, text="1. Wähle einen Compliance-Audit-Bericht:").pack(anchor="w")
        names = [p["name"] for p in audit_projekte]
        lb = tk.Listbox(parent, height=6)
        for n in names:
            lb.insert("end", n)
        lb.pack(fill="x", pady=4)

        # #705 — Auftragsverhältnis wählen
        art_frame = ttk.LabelFrame(parent, text="Verhältnis Audit ↔ Gutachten", padding=6)
        art_frame.pack(fill="x", pady=(4, 6))
        ttk.Radiobutton(
            art_frame, variable=state["einheitlich"], value=False,
            text="Separater Vor-Audit (Vorbefassung § 406 ZPO → Befangenheit für Gerichtsgutachten)",
        ).pack(anchor="w")
        ttk.Radiobutton(
            art_frame, variable=state["einheitlich"], value=True,
            text="Audit ist Teil dieses Gutachtens (einheitlicher Auftrag → keine Vorbefassung)",
        ).pack(anchor="w")

        info_frame = ttk.LabelFrame(parent, text="Audit-Summary + rechtlicher Hinweis", padding=8)
        info_frame.pack(fill="both", expand=True, pady=6)
        info_txt = tk.Text(info_frame, height=10, wrap="word")
        info_txt.pack(fill="both", expand=True)

        accept_cb = ttk.Checkbutton(
            parent,
            text="⚠ Ich verstehe den Vorbefassungs-Hinweis (§ 406 ZPO) und akzeptiere die Konsequenzen.",
            variable=state["acceptance"],
        )
        accept_cb.pack(anchor="w", pady=(6, 0))

        def _render_info() -> None:
            name = state.get("audit_name")
            if not name:
                return
            einheitlich = state["einheitlich"].get()
            state["warning"] = _a2pg.get_vorbefassungs_warning(
                audit_db, name, audit_teil_des_gutachtens=einheitlich)
            s = state["summary"] or {}
            w = state["warning"] or {}
            info = (
                f"{w.get('warning', '')}\n\n"
                f"────────────────\n"
                f"Firma: {s.get('firma', '—')}\n"
                f"Audit-Datum: {(s.get('created_at', '') or '')[:10]}\n"
                f"Frameworks: {', '.join(s.get('frameworks', [])) or '—'}\n"
                f"Anzahl Assessments: {s.get('anzahl_assessments', 0)}\n"
                f"Avg/Min-Score: {s.get('avg_score', '—')} / {s.get('min_score', '—')}\n"
                f"Befund-Kandidaten (Score<70): {len(state['gaps'])}"
            )
            info_txt.delete("1.0", "end")
            info_txt.insert("1.0", info)
            # Akzeptanz-Checkbox nur bei separater Vorbefassung relevant
            if einheitlich:
                accept_cb.state(["disabled"])
                state["acceptance"].set(False)
            else:
                accept_cb.state(["!disabled"])

        def on_pick(_evt=None) -> None:
            sel = lb.curselection()
            if not sel:
                return
            name = names[sel[0]]
            state["audit_name"] = name
            state["summary"] = _a2pg.get_audit_summary(audit_db, name)
            state["gaps"] = _a2pg.get_audit_gap_candidates(audit_db, name)
            state["selected_gaps"] = set(range(len(state["gaps"])))
            state["thema"].set(_a2pg.generate_pg_thema_from_audit(
                state["summary"], state["auftrags_art"].get()))
            if not state["pg_name"].get():
                from datetime import datetime as _dt
                state["pg_name"].set(f"PG-{_dt.now().year}-{name[:10]}")
            _render_info()

        lb.bind("<<ListboxSelect>>", on_pick)
        state["einheitlich"].trace_add("write", lambda *_: _render_info())

    def _wizard_step2(self, parent, state) -> None:
        rows = [
            ("PG-Name *", state["pg_name"]),
            ("SV-Name *", state["sv_name"]),
            ("Auftrags-Art", state["auftrags_art"]),
            ("Auftrags-Datum", state["auftrags_datum"]),
            ("Auftrags-Nummer", state["auftrags_nummer"]),
            ("Thema (auto)", state["thema"]),
            ("Honorarvereinbarung", state["honorar"]),
        ]
        for label, var in rows:
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, width=22).pack(side="left")
            if label.startswith("Auftrags-Art"):
                cb = ttk.Combobox(row, textvariable=var,
                                  values=["Tauglichkeitsprüfung", "Beweissicherung",
                                          "Schaden-Gutachten", "Wertgutachten",
                                          "Kaufberatung", "Sonstiges"], state="readonly")
                cb.pack(side="left", fill="x", expand=True)
            elif label.startswith("Thema"):
                ttk.Entry(row, textvariable=var, width=60).pack(side="left", fill="x", expand=True)
            else:
                ttk.Entry(row, textvariable=var, width=40).pack(side="left", fill="x", expand=True)

    def _wizard_step3(self, parent, state) -> None:
        ttk.Label(parent, text="Wähle Gaps (Score<70), die als leere Befund-Skeletons ins PG übernommen werden:",
                  wraplength=680).pack(anchor="w")
        ttk.Label(parent, text="⚠ Befund-Texte bleiben LEER (§ 407a ZPO — persönliche Neuformulierung Pflicht)",
                  foreground="#c62828").pack(anchor="w", pady=(0, 8))
        cols = ("sel", "section", "score", "comment")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c, lbl, w in [("sel", "☑", 30), ("section", "Section", 220),
                          ("score", "Score", 60), ("comment", "Kommentar", 360)]:
            tree.heading(c, text=lbl)
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True)
        for i, g in enumerate(state["gaps"]):
            sel = "✓" if i in state["selected_gaps"] else ""
            tree.insert("", "end", iid=str(i),
                        values=(sel, g.get("framework_section", ""),
                                f"{g.get('score', '?')}/100",
                                (g.get("comment") or "")[:100]))

        def toggle(_evt=None) -> None:
            for iid in tree.selection():
                idx = int(iid)
                if idx in state["selected_gaps"]:
                    state["selected_gaps"].remove(idx)
                    tree.set(iid, "sel", "")
                else:
                    state["selected_gaps"].add(idx)
                    tree.set(iid, "sel", "✓")

        tree.bind("<Double-1>", toggle)
        ttk.Label(parent, text="(Doppelklick zum Toggeln)", foreground="#666").pack(anchor="w")

    def _wizard_step4(self, parent, state, _audit_db, _dlg) -> None:
        info = (
            f"📋 Übernahme-Plan\n"
            f"────────────────\n"
            f"Audit-Quelle:       {state['audit_name']}\n"
            f"Neuer PG-Name:      {state['pg_name'].get()}\n"
            f"SV:                  {state['sv_name'].get()}\n"
            f"Auftrags-Art:        {state['auftrags_art'].get()}\n"
            f"Auftrags-Datum:      {state['auftrags_datum'].get()}\n"
            f"Auftrags-Nr.:        {state['auftrags_nummer'].get()}\n"
            f"Thema:               {state['thema'].get()[:200]}\n"
            f"Honorar:             {state['honorar'].get()[:100]}\n"
            f"Befund-Kandidaten:   {len(state['selected_gaps'])} von {len(state['gaps'])}\n\n"
            f"✓ Audit-Snapshot wird SHA-256-gesichert (Audit-Trail)\n"
            f"✓ Auftragsverhältnis: "
            + ("Audit ist Teil des Gutachtens — KEINE Vorbefassung (§ 406 ZPO)\n"
               if state["einheitlich"].get()
               else f"Separater Vor-Audit — Vorbefassung dokumentiert (akzeptiert: {state['acceptance'].get()})\n")
            + f"✓ § 407a-Disclaimer in jedem Befund-Skeleton\n"
        )
        if state.get("result"):
            info += f"\n────────────────\n✓ ERFOLGREICH ANGELEGT!\n"
            info += f"PG: {state['result'].get('pg_name', '')}\n"
            info += f"SHA-256: {(state['result'].get('audit_snapshot_sha256') or '')[:32]}…\n"
        t = tk.Text(parent, wrap="word", height=25)
        t.pack(fill="both", expand=True)
        t.insert("1.0", info)
        t.configure(state="disabled")

    def _wizard_execute(self, state, audit_db, dlg, render_fn) -> None:
        try:
            result = _a2pg.convert_audit_to_pg(
                audit_db,
                audit_projekt_name=state["audit_name"],
                pg_name=state["pg_name"].get().strip(),
                sv_name=state["sv_name"].get().strip(),
                auftrags_art=state["auftrags_art"].get(),
                auftrags_datum=state["auftrags_datum"].get(),
                auftrags_nummer=state["auftrags_nummer"].get(),
                honorarvereinbarung=state["honorar"].get(),
                thema=state["thema"].get(),
                befangenheits_akzeptanz=state["acceptance"].get() or state["einheitlich"].get(),
                audit_teil_des_gutachtens=state["einheitlich"].get(),
            )
            # Befund-Skeletons für ausgewählte Gaps
            for i, idx in enumerate(sorted(state["selected_gaps"])):
                gap = state["gaps"][idx]
                try:
                    _a2pg.create_befund_skeleton_from_gap(
                        audit_db, result["pg_name"], gap, f"B-{i + 1}")
                except Exception:
                    pass
            state["result"] = result
            render_fn()
            self._refresh_liste()
            messagebox.showinfo("Erfolg",
                                f"Privatgutachten '{result['pg_name']}' angelegt.\n"
                                f"{len(state['selected_gaps'])} Befund-Skeletons übernommen.",
                                parent=dlg)
        except Exception as e:
            messagebox.showerror("Konversions-Fehler", str(e), parent=dlg)
