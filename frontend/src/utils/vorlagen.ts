/**
 * Word-Vorlagen in der Oberfläche — welche kommt für welchen Bericht in Frage?
 *
 * Die Regel selbst gehört dem Server (`shared/reports/vorlagen.gilt_fuer_typ`
 * und `vorauswahl`); hier steht nur, **welche Einträge der Anwender sehen
 * darf**. Sie stand bis #2005 als Einzeiler im `ReportCenterPanel`, und mit der
 * Vorlagen-Auswahl am TOM-Generator wäre daraus eine zweite Kopie geworden —
 * die Spiegel-Liste aus #1731/#1735 in ihrer kleinsten Form.
 *
 * **Was hier NICHT steht: die Vorauswahl.** Die rechnet der Server und liefert
 * sie je Bericht als `vorlage_id` mit (#1703/S9, #1777). Dieselbe Rangfolge im
 * Browser nachzubauen heißt, dass Oberfläche und Export verschiedene Vorlagen
 * meinen — und auffallen würde das erst an zwei verschiedenen Dokumenten.
 */

import { t } from '../i18n'

export interface VorlagenEintrag {
  id: number
  name: string
  version?: number
  ist_default?: boolean
  /** Leer = gilt für alle Berichte des Moduls (Verhalten bis v8.0.3). */
  bericht_typ?: string
  firmen_id?: number | null
}

/** Die Vorlagen, die für den Bericht `typ` benutzbar sind. */
export function vorlagenFuerBericht<T extends VorlagenEintrag>(
  vorlagen: T[],
  typ: string,
): T[] {
  return (vorlagen || []).filter(v => !v.bericht_typ || v.bericht_typ === typ)
}

/** Beschriftung eines Eintrags im Auswahlfeld (eine Fassung für alle Masken). */
export function vorlageLabel(v: VorlagenEintrag): string {
  const teile = [v.name]
  if (v.version) teile.push(`v${v.version}`)
  if (v.firmen_id) teile.push(t('common.mandant'))
  if (!v.bericht_typ) teile.push(t('geteilt.reportCenterPanel.alleBerichte'))
  if (v.ist_default) teile.push(t('common.standard'))
  return `${teile[0]} · ${teile.slice(1).join(' · ')}`.replace(/ · $/, '')
}
