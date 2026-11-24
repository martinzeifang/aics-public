# Entscheidung: Navigations-Taxonomie & Sidebar (#1377 / #1378)

**Status:** entschieden · **Datum:** 2026-10-19 · **Sprint:** v7.3.0 · **Kontext:** Sprint #34 (Navigations-/Menü-Restrukturierung, #1369/#1376)

Beide Punkte sind P4-Spikes aus Sprint #34. Nach Einführung der gruppierten
Navigation (`GroupedModuleNav`, #1369) und der Tab-/Gruppen-Persistenz (#1376,
`nav:<modul>:tab` in localStorage, Deep-Link `?tab=` hat Vorrang) liegt eine
stabile, produktiv genutzte Taxonomie vor. Diese Entscheidung finalisiert sie.

## #1377 — Card-Sorting-Validierung der Gruppen-Taxonomie

**Entscheidung: aktuelle Zuordnung beibehalten.** Die gruppierte Navigation ist
seit Sprint #34 in CRA/NIS2/AI-Act/DSGVO/WiBA/RB im Einsatz; die Gruppen folgen
der jeweiligen regulatorischen Struktur (CRA: Kapitel/Annexe, NIS2: N1–N5, AI-Act:
HR/GOV/DATA/OPS, DSGVO: DSMS-Bereiche), die Anwender ohnehin aus der Norm kennen.
Ein formales Card-Sorting (NN/g) brächte gegenüber dieser normgetriebenen Gliederung
keinen belegbaren Mehrwert und wird nicht durchgeführt.

- Grenzfälle aus dem Issue bewusst so belassen: **SOC** `assets`/`uebungen` als
  eigene Betriebs-Gruppe; **CRA** `meldungen`/`korrektur` unter „Konformität &
  Meldung" (Art. 13/14-Nähe). Keine Umgruppierung nötig.
- Re-Evaluierung nur anlassbezogen (neues Modul oder > 3 neue Tabs je Gruppe).

## #1378 — Gruppierte Sidebar für 20+-Tab-Module (Spike)

**Entscheidung: bei der horizontalen, zweistufigen gruppierten Navigation bleiben;
keine separate collapsible Sidebar.** `GroupedModuleNav` skaliert durch Gruppen +
aktive Untertabs auch für tab-reiche Module (DSGVO) ausreichend; die
Tab-Persistenz (#1376) hält den Kontext über Reloads.

Trade-offs:

| Option | Pro | Contra |
|---|---|---|
| Horizontal, 2-stufig (Status quo) | eine Navigationskomponente für alle Module, konsistent, mobil ok | bei sehr vielen Gruppen horizontaler Scroll |
| Eigene collapsible Sidebar (DSGVO) | vertikale Skalierung | zweites Navigationsmuster, Sonderfall, höhere Wartung + Inkonsistenz |

Der Zusatznutzen rechtfertigt ein zweites Navigationsmuster nicht. Sollte ein Modul
künftig daurhaft > 6 Gruppen benötigen, wird dieser Punkt neu bewertet.
