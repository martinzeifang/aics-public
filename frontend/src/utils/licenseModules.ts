/**
 * Lizenz-Sichtbarkeit von Modulen — eine Stelle für die ganze Oberfläche (#1712).
 *
 * Vorher stand die Regel zweimal im Frontend (`AppLayout.visibleModules` und der
 * Router-Guard) und beide wichen vom Backend ab: beide prüften schlicht
 * „steht das Modul in `license_modules`?". Damit verschwanden **WiBA** und
 * **Risikobewertung** aus der Navigation, sobald eine Lizenz nur die
 * Zusatzmodule aufführte — obwohl beide zum Grundpreis gehören und jede gültige
 * Lizenz sie einschließt.
 *
 * Maßgeblich ist jetzt das Backend: `/api/auth/profile` liefert
 * `license_effective_modules` (aufgelöst über `shared/licensing/modules.py`).
 * Die Regeln hier unten sind nur der **Fallback** für einen veralteten
 * User-Objekt-Stand im Browser und spiegeln bewusst dieselbe Logik.
 */

/** Im Grundpreis enthalten — jede gültige Lizenz schließt sie ein. */
export const GRUNDPREIS_MODULE = [
  'risikobewertung', 'wiba', 'pentest', 'compliance_audit',
] as const

/** Mandantenregister — nie lizenz-gegated (Wiederanlauf muss möglich bleiben). */
export const UNGEGATETE_MODULE = ['firmen'] as const

/** Auch bei Wildcard `*` nur bei expliziter Nennung sichtbar. */
export const EXPLIZITE_MODULE = ['gutachten'] as const

/**
 * Ist das Modul laut Lizenz sichtbar?
 *
 * @param modulId Modul-Slug wie in der Navigation (`cra`, `wiba`, `aiact`, …)
 * @param user    das `user`-Objekt aus dem Auth-Store
 */
/**
 * Nav-Slug → kanonischer Lizenzschlüssel.
 *
 * Spiegelt `canonical()` aus `shared/licensing/modules.py`: Bindestriche werden
 * zu Unterstrichen, damit der Routen-Slug `compliance-audit` den Schlüssel
 * `compliance_audit` trifft.
 */
export function kanonisch(modulId: string): string {
  const key = (modulId || '').trim().toLowerCase().replace(/-/g, '_')
  return key === 'ai_act' ? 'aiact' : key
}

export function istModulLizenziert(modulId: string, user: unknown): boolean {
  const u = (user ?? {}) as Record<string, unknown>
  const key = kanonisch(modulId)

  // 1. Bevorzugt die vom Backend aufgelöste Liste (Single Source of Truth).
  const effektiv = u.license_effective_modules
  if (Array.isArray(effektiv)) {
    return effektiv.includes(key)
  }

  // 2. Fallback: Regeln aus shared/licensing/modules.py spiegeln.
  const licMods = u.license_modules
  if (!Array.isArray(licMods)) {
    // #1510: null/undefined = Lizenz nicht bestätigt → fail-OPEN (sichtbar).
    // Das Backend-Write-Gate erzwingt die Lizenz weiterhin; Sichtbarkeit ist
    // kein Schreibrecht.
    return true
  }
  if ((UNGEGATETE_MODULE as readonly string[]).includes(key)) return true
  if (licMods.length === 0) return false
  if ((EXPLIZITE_MODULE as readonly string[]).includes(key)) {
    return licMods.includes(key)
  }
  if ((GRUNDPREIS_MODULE as readonly string[]).includes(key)) return true
  return licMods.includes('*') || licMods.includes(key)
}
