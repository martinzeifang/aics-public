// #1460: Wandelt das (strukturierte) Parse-Ergebnis eines KI-Dokument-Assistenten
// in einen **formatierten Markdown-Bericht** — statt rohes JSON zu speichern.
//
// Reihenfolge:
//   1. liegt ein fertiges `markdown`-Feld vor → das gewinnt.
//   2. sonst aus den strukturierten Feldern einen Bericht bauen
//      (# Titel, Fließtext aus doc_text/text/…, übrige Felder als Abschnitte).
//   3. ist nur Roh-Text vorhanden: JSON → strukturiert rendern, sonst Text 1:1.

const META_KEYS = new Set(['markdown', 'applied', 'ok', 'error', 'doc_type'])
const TITLE_KEYS = ['titel', 'title', 'name', 'bezeichnung']
const BODY_KEYS = ['doc_text', 'markdown_text', 'text', 'inhalt', 'body', 'content', 'beschreibung']

function humanize(key: string): string {
  const s = key.replace(/_/g, ' ').trim()
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function valueToMd(v: any): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'string') return v.trim()
  if (typeof v === 'number' || typeof v === 'boolean') return String(v)
  if (Array.isArray(v)) {
    return v
      .map((x) => (x && typeof x === 'object' ? JSON.stringify(x) : String(x)))
      .filter((s) => s !== '')
      .map((s) => `- ${s}`)
      .join('\n')
  }
  // verschachteltes Objekt → Unter-Liste
  return Object.entries(v)
    .filter(([, val]) => val !== null && val !== undefined && val !== '')
    .map(([k, val]) => `- **${humanize(k)}:** ${typeof val === 'object' ? JSON.stringify(val) : val}`)
    .join('\n')
}

function objectToMarkdown(obj: Record<string, any>): string {
  const out: string[] = []
  const used = new Set<string>()

  const title = TITLE_KEYS.map((k) => obj[k]).find((v) => typeof v === 'string' && v.trim())
  if (title) { out.push(`# ${String(title).trim()}`); TITLE_KEYS.forEach((k) => used.add(k)) }

  const bodyKey = BODY_KEYS.find((k) => typeof obj[k] === 'string' && obj[k].trim())
  if (bodyKey) { out.push('', String(obj[bodyKey]).trim()); used.add(bodyKey) }

  for (const [k, v] of Object.entries(obj)) {
    if (used.has(k) || META_KEYS.has(k)) continue
    const md = valueToMd(v)
    if (!md) continue
    if (Array.isArray(v) || (v && typeof v === 'object')) out.push('', `## ${humanize(k)}`, md)
    else out.push('', `**${humanize(k)}:** ${md}`)
  }
  return out.join('\n').trim()
}

export function parsedToMarkdown(parsed: any, fallback = ''): string {
  if (parsed && typeof parsed === 'object'
      && typeof parsed.markdown === 'string' && parsed.markdown.trim()) {
    return parsed.markdown.trim()
  }
  let obj = parsed
  if (!obj || typeof obj !== 'object') {
    const raw = (fallback || '').trim()
    if (!raw) return ''
    try { obj = JSON.parse(raw) } catch { return raw } // kein JSON → bereits Text/Markdown
    if (!obj || typeof obj !== 'object') return raw
  }
  const md = objectToMarkdown(obj as Record<string, any>)
  return md || (fallback || '').trim()
}

export default parsedToMarkdown
