/**
 * Assistenten-Tab Registry (#1080 · Sprint #21, S10)
 *
 * Schema + helpers for the per-module "🤖 Assistenten" tab.
 *
 * This file only defines the data model + per-module assembly helpers. The
 * actual wiring into module panels (CRA / NIS2 / AI Act / DSGVO / …) happens in
 * Wave 2 — do NOT import this into any module panel yet.
 *
 * Backend-agnostic note: wizard descriptors are pure frontend metadata. They do
 * not perform any backend/GitHub access themselves; each wizard component is
 * responsible for its own (token-aware, #1064) API calls when opened.
 */

/** Coarse grouping shown as a section/badge inside the tile grid. */
export type AssistentKategorie =
  | 'dokumentation'
  | 'risiko'
  | 'compliance'
  | 'issues'
  | 'export'
  | 'sonstiges'

/**
 * A single wizard/assistant tile descriptor.
 *
 * `id` must be unique per module list — it is the value emitted by the grid's
 * `open` event so the hosting panel can decide which wizard to launch.
 */
export interface WizardDescriptor {
  /** Stable, unique identifier within a module (e.g. 'cra-risk-issue'). */
  id: string
  /** Short tile title. */
  title: string
  /** One-line description shown under the title. */
  description: string
  /** Category for grouping/badging. */
  kategorie: AssistentKategorie
  /** Emoji or short glyph rendered as the tile icon. */
  icon: string
  /**
   * Optional permission key required to use this wizard. When set, callers may
   * filter the list against the current user's permissions before rendering.
   */
  permission?: string
  /** When true the tile is shown but rendered disabled (e.g. coming soon). */
  disabled?: boolean
  /**
   * When set, the assistant produces a document that can be stored via the
   * generic Document-Management feature (Sprint #24, Block C). The grid then
   * offers a „📄 Als Dokument speichern" action for the wizard result.
   */
  produces_document?: { doc_type: string }
}

/**
 * Module identifiers that may expose an Assistenten tab. Kept as a string union
 * so Wave 2 can extend it without breaking existing callers.
 */
export type AssistentenModul =
  | 'cra'
  | 'nis2'
  | 'aiact'
  | 'dsgvo'
  | 'risikobewertung'
  | string

/** Human-readable labels for the known categories (German UI). */
export const KATEGORIE_LABELS: Record<AssistentKategorie, string> = {
  dokumentation: 'Dokumentation',
  risiko: 'Risiko',
  compliance: 'Compliance',
  issues: 'Issues',
  export: 'Export',
  sonstiges: 'Sonstiges',
}

/**
 * A per-module registry: maps a module id to its list of wizard descriptors.
 * Wave 2 populates this (or builds lists dynamically) and feeds it to the grid.
 */
export type WizardRegistry = Partial<Record<AssistentenModul, WizardDescriptor[]>>

/**
 * Build (and validate) a wizard list for a module.
 *
 * - Drops nothing automatically; instead it throws on duplicate `id`s so
 *   registration mistakes surface early during development.
 * - Returns a new, stable array (callers may safely mutate the result).
 */
export function buildWizardList(
  descriptors: readonly WizardDescriptor[],
): WizardDescriptor[] {
  const seen = new Set<string>()
  for (const d of descriptors) {
    if (seen.has(d.id)) {
      throw new Error(`buildWizardList: duplicate wizard id "${d.id}"`)
    }
    seen.add(d.id)
  }
  return [...descriptors]
}

/**
 * Resolve the wizard list for a given module from a registry, returning an
 * empty array when the module has no registered wizards.
 */
export function wizardsForModul(
  registry: WizardRegistry,
  modul: AssistentenModul,
): WizardDescriptor[] {
  return registry[modul] ?? []
}

/**
 * Filter a wizard list by the user's available permissions. Descriptors without
 * a `permission` are always kept. `permissions` may be any set-like collection.
 */
export function filterWizardsByPermission(
  wizards: readonly WizardDescriptor[],
  permissions: ReadonlySet<string> | readonly string[],
): WizardDescriptor[] {
  const allowed =
    permissions instanceof Set ? permissions : new Set(permissions)
  return wizards.filter((w) => !w.permission || allowed.has(w.permission))
}

/**
 * Group a wizard list by category, preserving insertion order within each
 * group and the canonical category order from {@link KATEGORIE_LABELS}.
 */
export function groupWizardsByKategorie(
  wizards: readonly WizardDescriptor[],
): Array<{ kategorie: AssistentKategorie; label: string; wizards: WizardDescriptor[] }> {
  const order = Object.keys(KATEGORIE_LABELS) as AssistentKategorie[]
  return order
    .map((kategorie) => ({
      kategorie,
      label: KATEGORIE_LABELS[kategorie],
      wizards: wizards.filter((w) => w.kategorie === kategorie),
    }))
    .filter((group) => group.wizards.length > 0)
}
