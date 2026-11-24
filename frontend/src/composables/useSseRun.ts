/**
 * #1573: Gemeinsamer POST-SSE-Konsument für alle KI-Streams
 * (Format von shared/sse.py: events phase/chunk/progress/done).
 *
 * Genutzt von KiStreamView (Live-Ansicht einer Bewertung) und vom
 * AutoMassBewertungModal (risikoweise/anforderungsweise Massenläufe). Ein
 * Stream pro Objekt statt eines langen Sammel-Requests → kein Browser-Timeout.
 */
import { bearerToken } from '../api/auth-token'
// `t` ist in dieser Maske schon belegt (lokale Variable/Parameter) —
// deshalb unter anderem Namen. Ein Import überdeckt eine lokale
// Bindung nicht, er kollidiert mit ihr: Der Aufruf trifft die
// Variable, und die ist keine Funktion. Gefunden hat das der
// Typprüfer (#1858), nicht der Build.
import { t as uebersetze } from '../i18n'

export type SseHandler = (event: string, data: any) => void

/**
 * Startet einen POST-SSE-Request und ruft `onEvent` je Event auf.
 * Liefert das Payload des finalen `done`-Events (oder `{ok:false,error}`).
 */
export async function runSse(url: string, body: any, onEvent?: SseHandler,
                             signal?: AbortSignal): Promise<any> {
  const token = bearerToken()  // #1190: zentraler Token-Zugriff (kein Web-Storage in Komponenten)
  if (!token) return { ok: false, error: uebersetze('ansichten.useSseRun.keinAuthTokenBitteNeuEinloggen') }
  let resp: Response
  try {
    resp = await fetch(url, {
      // #1964: Hier stand `uebersetze('common.pOST')`. Der i18n-Durchlauf hat
      // das Literal `'POST'` für einen Anzeigetext gehalten und in den Katalog
      // gezogen — wo der Schlüssel dann **nie angelegt** wurde. `t()` gibt für
      // einen unbekannten Schlüssel den Schlüssel zurück, also ging jede
      // Automatische KI-Bewertung mit der HTTP-Methode `common.pOST` hinaus.
      // Der Punkt ist ein erlaubtes Zeichen in einem Methoden-Token, der
      // Browser schickt sie also, und nginx weist sie ab, bevor eine
      // Request-Zeile entsteht: HTTP 400, im Zugriffslog nur `"-"`, in
      // `audit.log` gar nichts.
      //
      // **Eine HTTP-Methode ist kein Text für Menschen.** Sie gehört nie in
      // einen Katalog, und `tests/test_i18n_schluessel_1964.py` lässt rot
      // werden, wer das wieder tut.
      method: 'POST', signal,
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json',
                 Accept: 'text/event-stream' },
      body: JSON.stringify(body || {}),
    })
  } catch (e: any) {
    if (e?.name === 'AbortError') return { ok: false, error: uebersetze('ansichten.useSseRun.abgebrochen'), aborted: true }
    return { ok: false, error: `Netzwerk-Fehler: ${e?.message || e}` }
  }
  if (!resp.ok || !resp.body) {
    let d = ''
    try {
      const t = await resp.text()
      try { d = JSON.parse(t)?.error || t } catch { d = t }
    } catch { /* ignore */ }
    return { ok: false, error: `HTTP ${resp.status}${d ? ' — ' + String(d).slice(0, 300) : ''}` }
  }
  const reader = resp.body.getReader()
  const dec = new TextDecoder('utf-8')
  let buf = ''
  let final: any = null
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      let idx
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const raw = buf.slice(0, idx); buf = buf.slice(idx + 2)
        let ev = '', dataStr = ''
        for (const ln of raw.split('\n')) {
          if (ln.startsWith('event: ')) ev = ln.slice(7)
          else if (ln.startsWith('data: ')) dataStr += ln.slice(6)
        }
        if (!ev) continue
        let data: any = {}
        try { data = JSON.parse(dataStr) } catch { /* ignore */ }
        if (ev === 'done') final = data
        onEvent?.(ev, data)
      }
    }
  } catch (e: any) {
    if (e?.name === 'AbortError') return { ok: false, error: uebersetze('ansichten.useSseRun.abgebrochen'), aborted: true }
    return { ok: false, error: `Stream unterbrochen: ${e?.message || e}` }
  }
  return final || { ok: false, error: uebersetze('ansichten.useSseRun.streamOhneErgebnisBeendet') }
}
