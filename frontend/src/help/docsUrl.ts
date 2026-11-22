// Zentrale Basis-URL der öffentlichen Dokumentation (#1011).
// Eigene Datei (nicht index.ts), damit die Help-Module sie importieren können,
// ohne einen Zirkelimport mit index.ts (das die Help-Module einsammelt) zu erzeugen.
export const PUBLIC_DOCS_BASE_URL = 'https://aisuite.cyberwoks.de'

/** Baut eine absolute URL auf die öffentliche Doku, z. B. docsUrl('/modules/cra/'). */
export function docsUrl(path: string): string {
  return new URL(path, PUBLIC_DOCS_BASE_URL).toString()
}
