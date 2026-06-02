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
  /** Weiterführende Links */
  links?: HelpLink[]
}
