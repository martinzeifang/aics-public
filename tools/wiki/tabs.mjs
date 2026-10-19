// Autoritative Tab-Liste je Modul (id + exaktes Label inkl. Emoji, wie im UI gerendert).
// Reihenfolge = sinnvolle Doku-Reihenfolge.
export const MOD_TABS = {
  cra: [
    ['dashboard','📊 Dashboard'],['requirements','✅ Anforderungen'],['owasp','🛡️ OWASP SbD'],
    ['pflichtdoku','📋 Dokumentation'],['dokumente','📄 Dokumente'],['assistenten','🤖 Assistenten'],
    ['konformitaet','✅ Konformität'],['meldungen','🚨 Meldungen'],['akteure','🏷️ Akteure'],
    ['korrektur','↩️ Korrekturmaßnahmen'],['traceability','🔗 Traceability'],['fragebogen','📥 Fragebogen'],
    ['risikoanalyse','🔍 Risikoanalyse'],['risikocockpit','📊 Risiko-Cockpit'],['bericht','📄 Bericht'],
  ],
  nis2: [
    ['dashboard','📊 Dashboard'],['anforderungen','✅ Anforderungen'],['pflichtdoku','📋 Dokumentation'],
    ['dokumente','📄 Dokumente'],['assistenten','🤖 Assistenten'],['incidents','🚨 Vorfälle'],
    ['scoping','🎯 Scoping'],['registrierung','📝 Registrierung'],['audits','🔍 Audits'],
    ['governance','🏛️ Governance'],['fristen','📅 Fristen'],['dvo','📜 DVO 2690'],
    ['cockpit','📊 Risiko-Cockpit'],['bericht','📄 Bericht'],
  ],
  aiact: [
    ['dashboard','📊 Dashboard'],['anforderungen','✅ Anforderungen'],['art5','🚫 Art. 5 Verbote'],
    ['literacy','🎓 AI-Literacy'],['fria','⚖️ Art. 27 FRIA'],['conformity','🏷️ Art. 43/48 Konformität'],
    ['gpai','🧠 Art. 51-55 GPAI'],['owasp-llm','🛡️ OWASP-LLM'],['incidents','🚨 Art. 73 Vorfälle'],
    ['pflichtdoku','📋 Dokumentation'],['dokumente','📄 Dokumente'],['assistenten','🤖 Assistenten'],
    ['cockpit','📊 Risiko-Cockpit'],['bericht','📄 Bericht'],
  ],
  dsgvo: [
    ['dashboard','📊 Dashboard'],['anforderungen','✅ Anforderungen'],['pflichtdoku','📋 Dokumentation'],
    ['tom-katalog','🔐 TOM-Katalog'],['tom','🔒 TOM-Generator'],['betroffenenrechte','📨 Betroffenenrechte'],
    ['loeschkonzept','🗑️ Löschkonzept'],['transfer','🌍 Drittlandtransfer'],['einwilligung','✍️ Einwilligungen'],
    ['lia','⚖️ LIA-Register'],['zweckaenderung','🔄 Zweckänderung'],['subprozessoren','🔗 Subprozessoren'],
    ['joint-controller','🤝 Joint Controller'],['eu-vertreter','🇪🇺 EU-Vertreter'],['datenpannen','🚨 Datenpannen'],
    ['dsgvo-dsb','🛡️ DSB'],['privacy','📜 Datenschutzerklärung'],['training','🎓 Schulung'],
    ['kontrollen','🗓️ Kontrollen'],['jahresbericht','📅 Jahresbericht'],['berichte','📄 Berichte'],
    ['dokumente','📄 Dokumente'],['assistenten','🤖 Assistenten'],['cockpit','📊 Risiko-Cockpit'],
  ],
  wiba: [
    ['dashboard','📊 Dashboard'],['prueffragen','✅ Prüffragen'],['dokumentation','📋 Dokumentation'],
    ['dokumente','📄 Dokumente'],['assistenten','🤖 Assistenten'],['risikocockpit','📊 Risiko-Cockpit'],
    ['bericht','📄 Bericht'],
  ],
  soc: [
    ['dashboard','📊 Dashboard'],['reifegrad','📊 Reifegrad'],['alerts','🚨 Alarme'],
    ['incidents','🛡️ Incidents'],['vulnerabilities','🛡️ Schwachstellen'],['massnahmen','📋 Maßnahmen'],
    ['betrieb','📞 Betrieb'],['detektion','🛰️ Detektion'],['threatintel','🌐 Threat-Intel'],
    ['hunting','🔭 Hunting'],['logquellen','📡 Log-Quellen'],['assets','🖥️ Assets'],
    ['uebungen','🎯 Übungen'],['assistenten','🤖 Assistenten'],['berichte','📑 Berichte'],['setup','⚙️ Einrichtung'],
  ],
  risikobewertung: [
    ['dashboard','📊 Dashboard'],['risiken','⚠️ Risiken'],['cockpit','📊 Risiko-Cockpit'],['bericht','📄 Bericht'],
  ],
}
