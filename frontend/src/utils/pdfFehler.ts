/**
 * Eine Lesart für PDF-Fehlerantworten (#1903).
 *
 * **Der Befund:** Neun Stellen übersetzten `status === 503` blind in
 * „PDF-Konverter nicht verfügbar — bitte DOCX nutzen." Auf Produktiv war der
 * Konverter verfügbar; ein hängender LibreOffice ließ jede Umwandlung mit
 * HTTP 500 scheitern. Der Anwender bekam einen Weg genannt, der die Ursache
 * nicht berührt — und bei den fünf DSGVO-Endpunkten gar diesen Text nicht
 * einmal, weil sie tatsächlich 500 lieferten.
 *
 * Seit #1903 unterscheidet der Server drei Fälle und **nennt den Grund**
 * (503 nicht erreichbar · 504 Zeitlimit · 502 Konverter lehnt ab). Damit ist
 * die Frage im Frontend nicht mehr „welchen Text erfinde ich für 503?", sondern
 * „wie komme ich an die Aussage des Servers?".
 *
 * **Und das ist die eigentliche Arbeit hier:** Alle Export-Aufrufe laufen mit
 * `responseType: 'blob'`. Eine Fehlerantwort ist dann ein *Blob* und nicht das
 * geparste JSON — `e.response.data.error` ist `undefined`. Genau daran wäre die
 * ganze Verbesserung hängen geblieben: Der Server hätte die richtige Meldung
 * geschickt und niemand hätte sie gesehen (dieselbe Form wie #1735, wo die
 * Vorlage nur im Test-Export wirkte, und #1841, wo das Budget nie ankam).
 */

/** Maschinenlesbare Kennungen des Servers (siehe `shared/pdf_fehler.py`). */
export const PDF_CODES = {
  nichtErreichbar: 'pdf-konverter-nicht-erreichbar',
  zeitlimit: 'pdf-zeitlimit',
  fehlgeschlagen: 'pdf-umwandlung-fehlgeschlagen',
} as const

interface PdfFehlerAntwort {
  error?: string
  code?: string
  grund?: string
  hinweis?: string
  timeout_s?: number
}

/**
 * Packt die Fehlerantwort aus — auch aus einem Blob.
 *
 * Liefert `{}`, wenn nichts Lesbares drinsteht; der Aufrufer fällt dann auf
 * seinen eigenen Text zurück.
 */
export async function fehlerAntwort(e: any): Promise<PdfFehlerAntwort> {
  const daten = e?.response?.data
  if (!daten) return {}
  // Normalfall: Axios hat JSON geparst.
  if (typeof daten === 'object' && !(daten instanceof Blob)) {
    return daten as PdfFehlerAntwort
  }
  // Download-Fall: `responseType: 'blob'` liefert auch den Fehler als Blob.
  if (daten instanceof Blob) {
    try {
      const text = await daten.text()
      if (!text) return {}
      return JSON.parse(text) as PdfFehlerAntwort
    } catch {
      // Kein JSON (z. B. eine nginx-Fehlerseite) → nichts zu holen.
      return {}
    }
  }
  if (typeof daten === 'string') {
    try {
      return JSON.parse(daten) as PdfFehlerAntwort
    } catch {
      return {}
    }
  }
  return {}
}

/** True, wenn die Antwort von einem PDF-Fehler des Servers stammt. */
export function istPdfFehler(status: number | undefined, a: PdfFehlerAntwort): boolean {
  if (a.code && Object.values(PDF_CODES).includes(a.code as any)) return true
  return status === 502 || status === 503 || status === 504
}

/**
 * Text für den Anwender.
 *
 * Vorrang hat **immer** die Aussage des Servers: Nur er weiß, ob der Konverter
 * nicht erreichbar war, zu lange gebraucht hat oder die Umwandlung abgelehnt
 * hat — und nur er kennt den Grund. Die Zuordnung nach Status ist der Rückfall
 * für einen Server, der noch älter ist als dieser Code (Mischbetrieb während
 * eines Deploys).
 */
export async function pdfFehlerText(e: any, fallback = 'Export fehlgeschlagen.'): Promise<string> {
  const status = e?.response?.status as number | undefined
  const a = await fehlerAntwort(e)

  if (a.error) {
    // `grund` ist der Klartext des Konverters. Er steht in Klammern dahinter,
    // weil er technisch ist — aber er steht da: Sein Fehlen hat die Suche bei
    // #1903 in die falsche Richtung geschickt.
    return [a.error, a.grund ? `(${a.grund})` : '', a.hinweis || '']
      .filter(Boolean)
      .join(' ')
  }

  if (!istPdfFehler(status, a)) {
    return e?.message ? `${fallback} (${e.message})` : fallback
  }

  if (status === 504) {
    return 'Die Umwandlung in PDF hat zu lange gedauert und wurde abgebrochen. ' +
      'Bei einem sehr großen Dokument hilft der Word-Export (DOCX).'
  }
  if (status === 502) {
    return 'Der PDF-Konverter hat die Umwandlung abgelehnt. ' +
      'Das Word-Dokument (DOCX) lässt sich weiter herunterladen.'
  }
  return 'Der PDF-Konverter ist nicht erreichbar. ' +
    'Das Word-Dokument (DOCX) lässt sich weiter herunterladen.'
}
