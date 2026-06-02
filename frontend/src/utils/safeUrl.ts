/**
 * safeUrl — Schema-Allowlist für aus DB/User stammende Links (Issue #746, WP-13).
 *
 * Wird ein `:href` an Werte gebunden, die aus der Datenbank oder von Nutzenden
 * stammen, könnte dort `javascript:…` oder ein anderes gefährliches Schema stehen
 * (DOM-XSS bei Klick). Diese Funktion lässt nur http(s) (und mailto) zu und gibt
 * sonst ein neutrales `#` zurück.
 *
 * OWASP A03 (Injection).
 */
const ALLOWED_SCHEMES = ['http:', 'https:', 'mailto:']

/**
 * Liefert die URL zurück, wenn ihr Schema erlaubt ist, sonst '#'.
 * Relative URLs (ohne Schema) werden durchgelassen.
 * @param url potenziell unsichere URL aus DB/User-Eingabe
 */
export function safeUrl(url: string | null | undefined): string {
  if (!url) return '#'
  const trimmed = String(url).trim()
  if (!trimmed) return '#'
  // Relative/anker-URLs ohne Schema erlauben (kein ":" vor erstem "/", "?" oder "#").
  const schemeMatch = trimmed.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):/)
  if (!schemeMatch) return trimmed
  const scheme = schemeMatch[1].toLowerCase() + ':'
  return ALLOWED_SCHEMES.includes(scheme) ? trimmed : '#'
}

export default safeUrl
