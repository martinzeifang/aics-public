/**
 * markdownToHtml — minimaler Markdown→HTML-Konverter (Sprint #24, Block C).
 *
 * Das Projekt hat keine `marked`/`markdown-it`-Dependency. Assistenten-Ergebnisse
 * sind i.d.R. einfacher Markdown-Text (Überschriften, Listen, Fett/Kursiv,
 * Absätze). Diese Funktion deckt genau dieses Teilset ab und leitet das Ergebnis
 * anschließend durch {@link sanitizeHtml} (DOMPurify) — passend zur Allowlist des
 * Tiptap-Editors, in dem die Dokumente weiterbearbeitet werden.
 *
 * Kein vollwertiger Markdown-Parser; bei reinem Text wird der Inhalt sicher in
 * Absätze gehüllt.
 */
import sanitizeHtml from './sanitizeHtml'

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/** Inline-Formatierung (fett, kursiv, code, Links) auf bereits escaptem Text. */
function inline(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>')
    .replace(/(^|[^_])_([^_]+)_/g, '$1<em>$2</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
}

/**
 * Konvertiert (vereinfachten) Markdown-Text in sicheres HTML für den Editor.
 */
export function markdownToHtml(md: string | null | undefined): string {
  if (!md) return ''
  const lines = escapeHtml(md.replace(/\r\n/g, '\n')).split('\n')
  const out: string[] = []
  let listType: 'ul' | 'ol' | null = null
  let paragraph: string[] = []

  const flushParagraph = () => {
    if (paragraph.length) {
      out.push(`<p>${inline(paragraph.join(' '))}</p>`)
      paragraph = []
    }
  }
  const closeList = () => {
    if (listType) {
      out.push(`</${listType}>`)
      listType = null
    }
  }

  for (const raw of lines) {
    const line = raw.trimEnd()

    // Leerzeile → Absatz/Liste schließen
    if (!line.trim()) {
      flushParagraph()
      closeList()
      continue
    }

    // Überschriften
    const h = line.match(/^(#{1,6})\s+(.*)$/)
    if (h) {
      flushParagraph()
      closeList()
      const level = Math.min(h[1].length, 6)
      out.push(`<h${level}>${inline(h[2].trim())}</h${level}>`)
      continue
    }

    // Aufzählung
    const ul = line.match(/^\s*[-*+]\s+(.*)$/)
    if (ul) {
      flushParagraph()
      if (listType !== 'ul') {
        closeList()
        listType = 'ul'
        out.push('<ul>')
      }
      out.push(`<li>${inline(ul[1].trim())}</li>`)
      continue
    }

    // Nummerierung
    const ol = line.match(/^\s*\d+[.)]\s+(.*)$/)
    if (ol) {
      flushParagraph()
      if (listType !== 'ol') {
        closeList()
        listType = 'ol'
        out.push('<ol>')
      }
      out.push(`<li>${inline(ol[1].trim())}</li>`)
      continue
    }

    // sonst: Absatztext (mehrere Zeilen zusammenführen)
    closeList()
    paragraph.push(line.trim())
  }

  flushParagraph()
  closeList()

  return sanitizeHtml(out.join('\n'))
}

export default markdownToHtml
