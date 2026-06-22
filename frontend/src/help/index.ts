// Registry der Modul-Hilfe (#926/#927).
import type { ModuleHelp } from './types'
import { craHelp } from './cra'
import { nis2Help } from './nis2'
import { aiactHelp } from './aiact'
import { dsgvoHelp } from './dsgvo'
import { gutachtenHelp } from './gutachten'
import { risikobewertungHelp } from './risikobewertung'
import { firmenHelp } from './firmen'
import { wibaHelp } from './wiba'
import { socHelp } from './soc'

export const MODULE_HELP: Record<string, ModuleHelp> = {
  cra: craHelp,
  nis2: nis2Help,
  aiact: aiactHelp,
  dsgvo: dsgvoHelp,
  gutachten: gutachtenHelp,
  risikobewertung: risikobewertungHelp,
  firmen: firmenHelp,
  wiba: wibaHelp,
  soc: socHelp,
}

export function getModuleHelp(module: string): ModuleHelp | null {
  return MODULE_HELP[module] ?? null
}

// Öffentliche Doku-URL + Helper (#1011) — re-exportiert aus ./docsUrl
export { PUBLIC_DOCS_BASE_URL, docsUrl } from './docsUrl'

export type { ModuleHelp } from './types'
