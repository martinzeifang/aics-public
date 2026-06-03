// Registry der Modul-Hilfe (#926/#927).
import type { ModuleHelp } from './types'
import { craHelp } from './cra'
import { nis2Help } from './nis2'
import { aiactHelp } from './aiact'
import { dsgvoHelp } from './dsgvo'
import { doraHelp } from './dora'
import { gutachtenHelp } from './gutachten'
import { risikobewertungHelp } from './risikobewertung'
import { firmenHelp } from './firmen'

export const MODULE_HELP: Record<string, ModuleHelp> = {
  cra: craHelp,
  nis2: nis2Help,
  aiact: aiactHelp,
  dsgvo: dsgvoHelp,
  dora: doraHelp,
  gutachten: gutachtenHelp,
  risikobewertung: risikobewertungHelp,
  firmen: firmenHelp,
}

export function getModuleHelp(module: string): ModuleHelp | null {
  return MODULE_HELP[module] ?? null
}

export type { ModuleHelp } from './types'
