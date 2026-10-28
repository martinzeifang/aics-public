/**
 * #1573: Adapter für die EINHEITLICHE Massenbewertung in allen Modulen.
 *
 * Ein Adapter beschreibt, welche Objekte ein Modul bewertet und welche Endpunkte
 * Sammel-Prompt / Vorschau / Übernahme bedienen. Dadurch nutzen CRA, NIS2, AI Act,
 * DSGVO, WiBA und Risikobewertung denselben Dialog (MassAssessmentModal) und dieselbe
 * automatische Massenbewertung (AutoMassBewertungModal).
 */
import apiClient from '../api/client'
import type { AutoMassItem } from './autoBewertung'

// Eine Stelle fürs ganze Frontend (#1850) — vorher stand die
// Zeichenkette hier und an vier weiteren Orten.
import { NEUBEWERTUNG_MARKER as REASSESS } from './neubewertung'

export interface MassPreviewRow {
  id: string
  code: string
  label: string
  /** neuer Wert laut KI-Antwort, z. B. „4/5", „Hoch (16)", „Ja" */
  neu: string
  text: string
  data: any
}

export interface MassAdapter {
  objekt: string
  objekte: string
  /**
   * #1835: Modulschlüssel für die gespeicherten Prompt-Hinweise. Steht hier,
   * weil der Adapter die einzige Stelle ist, die das Modul schon kennt — aus
   * einer URL zu raten wäre eine zweite Wahrheit (`cra-konformitaet` ist nicht
   * `cra`).
   */
  modul: string
  wertLabel: string
  items: AutoMassItem[]
  responsePlaceholder: string
  /** Stream-URL der automatischen Einzelbewertung (auch für den Massenlauf) */
  streamUrl: (id: string | number) => string
  prompt(ids: string[]): Promise<{ prompt: string; count: number }>
  preview(raw: string): Promise<{ rows: MassPreviewRow[]; unknown: (string | number)[] }>
  apply(rows: MassPreviewRow[]): Promise<{ ok: number; total: number }>
}

const enc = encodeURIComponent

async function applyEach(rows: MassPreviewRow[], fn: (r: MassPreviewRow) => Promise<unknown>) {
  let ok = 0
  for (const r of rows) {
    try { await fn(r); ok++ } catch { /* einzelner Fehler stoppt nicht den Rest */ }
  }
  return { ok, total: rows.length }
}

/** CRA / NIS2 / AI Act / DSGVO — Anforderungen mit Score 0–5. */
export function requirementAdapter(apiBase: string, projekt: string, reqs: any[]): MassAdapter {
  const base = `${apiBase}/projekte/${enc(projekt)}`
  return {
    objekt: 'Anforderung', objekte: 'Anforderungen', wertLabel: 'Bewertung',
    modul: apiBase.replace(/^\//, ''),
    items: (reqs || []).map((r: any) => {
      const score = Number(r.bewertung ?? r.score ?? 0) || 0
      return {
        id: String(r.id), code: String(r.id), label: String(r.titel || r.title || ''),
        wert: `${score}/5`, open: score < 5,
        reassess: String(r.kommentar ?? r.notiz ?? '').includes(REASSESS),
      }
    }),
    responsePlaceholder: '[{"id":"…","score":4,"kommentar":"…","massnahmen":["…"]}]',
    streamUrl: id => `/api${base}/anforderungen/${enc(String(id))}/auto-bewertung/stream`,
    async prompt(ids) {
      const res = await apiClient.post(`${base}/anforderungen/mass-prompt`, { req_ids: ids })
      return { prompt: res.data.prompt, count: res.data.count }
    },
    async preview(raw) {
      const res = await apiClient.post(`${base}/anforderungen/mass-preview`, { response: raw })
      return {
        rows: (res.data.items || []).map((p: any) => ({
          id: String(p.id), code: String(p.id), label: p.titel || '',
          neu: `${p.bewertung}/5`, text: p.kommentar || '', data: p,
        })),
        unknown: res.data.unknown || [],
      }
    },
    apply: rows => applyEach(rows, r => apiClient.post(`${base}/bewertungen`, {
      anforderung_id: r.data.id, bewertung: r.data.bewertung, kommentar: r.data.kommentar,
      massnahme: r.data.massnahme || '',
    })),
  }
}

const WIBA_LABEL: Record<string, string> = { offen: 'Offen', ja: 'Ja', nein: 'Nein', nicht_relevant: 'Nicht relevant' }

/** WiBA — Prüffragen mit BSI-Antwortmodell (ja/nein/nicht relevant). */
export function wibaAdapter(projekt: string, controls: any[]): MassAdapter {
  const base = `/wiba/projekte/${enc(projekt)}`
  return {
    objekt: 'Prüffrage', objekte: 'Prüffragen', wertLabel: 'Antwort',
    modul: 'wiba',
    items: (controls || []).map((c: any) => ({
      id: String(c.control_id), code: String(c.control_id), label: String(c.frage || ''),
      wert: WIBA_LABEL[c.status || 'offen'] || c.status, open: (c.status || 'offen') === 'offen',
      reassess: String(c.notiz || '').includes(REASSESS),
    })),
    responsePlaceholder: '[{"control_id":"…","status":"ja|nein|nicht_relevant","notiz":"…"}]',
    streamUrl: id => `/api${base}/controls/${enc(String(id))}/auto-bewertung/stream`,
    async prompt(ids) {
      const res = await apiClient.post(`${base}/controls/mass-prompt`, { control_ids: ids })
      return { prompt: res.data.prompt, count: res.data.count }
    },
    async preview(raw) {
      const res = await apiClient.post(`${base}/controls/mass-preview`, { response: raw })
      return {
        rows: (res.data.items || []).map((p: any) => ({
          id: String(p.control_id), code: String(p.control_id), label: p.frage || '',
          neu: WIBA_LABEL[p.status] || p.status, text: p.notiz || '', data: p,
        })),
        unknown: res.data.unknown || [],
      }
    },
    apply: rows => applyEach(rows, r => apiClient.post(`${base}/antworten`, {
      control_id: r.data.control_id, status: r.data.status, notiz: r.data.notiz || '',
    })),
  }
}

/** Risikobewertung — Risiken mit framework-spezifischen Feldern (erledigte ausgenommen). */
export function risikoAdapter(projekt: string, risiken: any[]): MassAdapter {
  const base = `/risikobewertung/projekte/${enc(projekt)}`
  return {
    objekt: 'Risiko', objekte: 'Risiken', wertLabel: 'Risiko',
    modul: 'risikobewertung',
    items: (risiken || []).filter((r: any) => !r.is_resolved).map((r: any) => ({
      id: String(r.id), code: `#${r.nr ?? r.id}`, label: String(r.risk_name || ''),
      wert: r.risiko_label ? `${r.risiko_label}${r.risikowert != null ? ` (${r.risikowert})` : ''}` : 'unbewertet',
      open: !r.risiko_label,
      reassess: String(r.bewertung_text || '').includes(REASSESS),
    })),
    responsePlaceholder: '[{"nr":1,"felder":{…},"bewertung":"…"}]',
    streamUrl: id => `/api${base}/risiken/${enc(String(id))}/ollama/stream`,
    async prompt(ids) {
      const res = await apiClient.post(`${base}/risiken/mass-assess-prompt`,
        { risk_ids: ids.map(Number), only_open: false })
      return { prompt: res.data.prompt, count: res.data.count }
    },
    async preview(raw) {
      const res = await apiClient.post(`${base}/risiken/mass-assess-preview`, { raw })
      return {
        rows: (res.data.assessments || []).map((a: any) => ({
          id: String(a.risk_id), code: `#${a.nr}`, label: a.risk_name || '',
          neu: a.risiko_label ? `${a.risiko_label} (${a.risikowert ?? '–'})` : '—',
          text: a.bewertung_text || '', data: a,
        })),
        unknown: res.data.unmatched || [],
      }
    },
    async apply(rows) {
      const res = await apiClient.post(`${base}/risiken/mass-assess-apply`,
        { assessments: rows.map(r => r.data) })
      return { ok: Number(res.data.applied_count || 0), total: rows.length }
    },
  }
}

/**
 * OWASP-Kontrollen (CRA `owasp`, AI-Act `owasp-llm`) — nur automatische Bewertung
 * (kein Sammel-Prompt-Endpunkt). Score 0–5 wie Anforderungen.
 */
export function owaspAutoAdapter(apiBase: string, pfad: 'owasp' | 'owasp-llm', projekt: string,
                                 controls: { id: string; title: string; score: number; kommentar?: string }[]): MassAdapter {
  const unsupported = () => Promise.reject(new Error('Sammel-Prompt für OWASP-Kontrollen nicht verfügbar'))
  return {
    objekt: pfad === 'owasp' ? 'OWASP-Kontrolle' : 'OWASP-LLM-Kontrolle',
    objekte: pfad === 'owasp' ? 'OWASP-Kontrollen' : 'OWASP-LLM-Kontrollen',
    wertLabel: 'Bewertung',
    modul: apiBase.replace(/^\//, ''),
    items: (controls || []).map(c => {
      const score = Number(c.score ?? 0) || 0
      return { id: c.id, code: c.id, label: c.title, wert: `${score}/5`, open: score < 5,
               reassess: String(c.kommentar || '').includes(REASSESS) }
    }),
    responsePlaceholder: '',
    streamUrl: id => `/api${apiBase}/projekte/${enc(projekt)}/${pfad}/${enc(String(id))}/auto-bewertung/stream`,
    prompt: unsupported, preview: unsupported, apply: unsupported,
  }
}
