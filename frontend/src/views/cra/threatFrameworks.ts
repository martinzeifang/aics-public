
import { t } from '../../i18n'
// Einheitliche C5-Threat-Model-Framework-Liste (#938).
// Muss mit cra/threat_frameworks.py (Backend Single Source of Truth) übereinstimmen.

export interface ThreatFramework {
  id: string
  label: string
}

export const THREAT_FRAMEWORKS: ThreatFramework[] = [
  { id: t('common.sTRIDE'), label: t('cra.threatFrameworks.sTRIDEMicrosoftSDL') },
  { id: t('cra.threatFrameworks.sTRIDELLM'), label: t('cra.threatFrameworks.sTRIDELLMOWASPLLMTop') },
  { id: t('cra.threatFrameworks.pASTA'), label: 'PASTA (risiko-/business-zentriert)' },
  { id: t('cra.threatFrameworks.lINDDUN'), label: 'LINDDUN (Privacy)' },
  { id: t('cra.threatFrameworks.hEAVENS'), label: 'HEAVENS (Embedded/Automotive)' },
  { id: t('cra.threatFrameworks.oCTAVE'), label: t('cra.threatFrameworks.oCTAVEAllegroCERTCMU') },
  { id: t('cra.threatFrameworks.tARA'), label: 'TARA (ISO/SAE 21434)' },
  { id: t('cra.threatFrameworks.finanzinstitute'), label: t('cra.threatFrameworks.risikobewertungFinanzinstitute') },
]
