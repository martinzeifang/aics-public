// Einheitliche C5-Threat-Model-Framework-Liste (#938).
// Muss mit cra/threat_frameworks.py (Backend Single Source of Truth) übereinstimmen.

export interface ThreatFramework {
  id: string
  label: string
}

export const THREAT_FRAMEWORKS: ThreatFramework[] = [
  { id: 'STRIDE', label: 'STRIDE (Microsoft SDL)' },
  { id: 'STRIDE-LLM', label: 'STRIDE-LLM (OWASP LLM Top 10)' },
  { id: 'PASTA', label: 'PASTA (risiko-/business-zentriert)' },
  { id: 'LINDDUN', label: 'LINDDUN (Privacy)' },
  { id: 'HEAVENS', label: 'HEAVENS (Embedded/Automotive)' },
  { id: 'OCTAVE', label: 'OCTAVE Allegro (CERT/CMU)' },
  { id: 'TARA', label: 'TARA (ISO/SAE 21434)' },
  { id: 'Finanzinstitute', label: 'Risikobewertung Finanzinstitute' },
]
