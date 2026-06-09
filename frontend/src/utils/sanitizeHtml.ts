/**
 * sanitizeHtml — zentrale XSS-Härtung für Rich-Text-Rendering (Issue #740, WP-07).
 *
 * Jedes `v-html` MUSS HTML durch diese Funktion leiten. Die Allowlist entspricht
 * den Tags, die der Tiptap-StarterKit (+ Underline) erzeugt. Gefährliche Elemente
 * wie <img>, <script>, Event-Handler (onerror, onclick, …) und das style-Attribut
 * werden entfernt; `javascript:`-URLs werden gestrippt.
 *
 * OWASP A03 (Injection) / A05 (Security Misconfiguration) / A07.
 */
import DOMPurify from 'dompurify'

// Tags, die Tiptap StarterKit + Underline produziert.
const ALLOWED_TAGS = [
  'p', 'br',
  'strong', 'b', 'em', 'i', 'u', 's',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'ul', 'ol', 'li',
  'blockquote', 'code', 'pre',
  'a', 'span',
]

// Nur unkritische Attribute. KEIN style, KEIN on*-Handler.
const ALLOWED_ATTR = ['href', 'target', 'rel', 'class']

/**
 * Bereinigt unsicheres HTML zu einem sicheren Teilset.
 * @param dirty potenziell unsicheres HTML (z. B. aus der DB / Editor)
 * @returns bereinigtes HTML, gefahrlos für v-html
 */
export function sanitizeHtml(dirty: string | null | undefined): string {
  if (!dirty) return ''
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    // <img> & Event-Handler explizit verbieten (Akzeptanzkriterium #740).
    FORBID_TAGS: ['img', 'script', 'style', 'iframe', 'object', 'embed'],
    FORBID_ATTR: ['style', 'onerror', 'onload', 'onclick'],
    // javascript:/data: URLs in href etc. unterbinden.
    ALLOW_DATA_ATTR: false,
    USE_PROFILES: { html: true },
  })
}

export default sanitizeHtml
