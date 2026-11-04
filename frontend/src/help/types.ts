// Typen für die modulübergreifende Hilfe (#926).

export interface HelpSection {
  title: string
  intro?: string
  bullets?: string[]
}

export interface FrameworkInfo {
  name: string
  ref: string
  whenToUse: string
}

export interface HelpLink {
  label: string
  href: string
}

/**
 * Bereichsgenauer Ausfüll-Leitfaden für einen Tab/Bereich eines Moduls (#1223).
 * Damit ein Fachkundiger jeden Pflicht-/Bericht-/Options-Bereich korrekt befüllt.
 */
export interface HelpArea {
  /** == Tab-id im jeweiligen *View.vue (für kontext-sensitives Öffnen) */
  id: string
  /** Tab-Label/Bereichsname */
  title: string
  /** Wofür dieser Bereich da ist */
  zweck: string
  /** Konkrete Rechtsgrundlage (Artikel/Norm), falls einschlägig */
  rechtsgrundlage?: string
  /** Pflichtangaben/-felder + was hineingehört */
  pflichtfelder: string[]
  /** Schritt-für-Schritt zum korrekten Ausfüllen */
  anleitung?: string
  /** Praxis-Tipps / häufige Fehler */
  tipps?: string[]
}

export interface ModuleHelp {
  /** Schlüssel (z. B. 'cra', 'risikobewertung') */
  module: string
  /** Anzeigename */
  title: string
  /** Zugrundeliegende Verordnung/Richtlinie/Norm inkl. Nummer */
  regulation: string
  /** Kurzbeschreibung, worum es geht */
  purpose: string
  /** Gesetzlicher Rahmen — was die Regulierung verlangt */
  legalBasis: HelpSection
  /** Allgemeine Umsetzungshinweise / Workflow */
  implementation: HelpSection
  /** Modul-spezifische Hinweise */
  moduleSpecific?: HelpSection
  /** Nur Risikobewertung: Framework-Übersicht (wann welches sinnvoll) */
  frameworks?: FrameworkInfo[]
  /** Bereichsgenaue Ausfüll-Leitfäden je Tab (#1223) */
  areas?: HelpArea[]
  /** Weiterführende Links */
  links?: HelpLink[]
}
