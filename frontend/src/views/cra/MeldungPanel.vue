<template>
  <div class="meldung-panel">
    <div class="panel-header">
      <h3>🚨 Art. 14 — Melde-Workflow</h3>
      <p class="sub">Aktiv ausgenutzte Schwachstellen + schwerwiegende Vorfälle ·
        Frühwarnung 24h → Meldung 72h → Abschluss 14d/1M · gleichzeitig an
        CSIRT-Koordinator und ENISA (ENISA SRP)</p>
    </div>

    <div v-if="store.error" class="alert alert-error">{{ store.error }}</div>

    <button class="btn-primary" @click="showForm = !showForm">+ Neue Meldung</button>

    <div v-if="showForm" class="form-card">
      <div class="form-grid">
        <div class="form-row">
          <label>Typ</label>
          <select v-model="form.typ">
            <option value="vuln_exploited">Aktiv ausgenutzte Schwachstelle (Abschluss 14d)</option>
            <option value="serious_incident">Schwerwiegender Vorfall (Abschluss 1 Monat)</option>
          </select>
        </div>
        <div class="form-row">
          <label>Titel</label>
          <input v-model="form.titel" placeholder="Kurzbeschreibung" />
        </div>
        <div class="form-row">
          <label>Erkannt am</label>
          <input v-model="form.erkannt_am" type="datetime-local" />
        </div>
        <div class="form-row">
          <label>Betroffene Mitgliedstaaten</label>
          <input v-model="form.betroffene_ms" placeholder="z.B. DE, FR" />
        </div>
      </div>
      <button class="btn-primary" @click="create">Speichern</button>
      <button class="btn-secondary" @click="showForm = false">Abbrechen</button>
    </div>

    <table v-if="store.meldungen.length" class="meldung-table">
      <thead>
        <tr>
          <th>Titel</th><th>Typ</th><th>Status</th><th>Fristen-Ampel</th>
          <th>Nachweis</th><th>Aktionen</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="m in store.meldungen" :key="m.id">
          <tr>
            <td>{{ m.titel }}</td>
            <td>{{ m.typ === 'serious_incident' ? 'Vorfall' : 'Schwachstelle' }}</td>
            <td>{{ statusLabel(m.status) }}</td>
            <td>
              <span v-for="s in m.deadlines?.stages || []" :key="s.key"
                    class="ampel" :class="'ampel-' + s.ampel" :title="ampelTitle(s)">
                {{ s.label }}
              </span>
            </td>
            <td>
              <span v-if="!m.nachweis" class="nachweis-badge offen">—</span>
              <!-- #1760: Eine Akte, in der noch nichts gemeldet wurde, hat keine
                   Lücke — und sah deshalb aus wie „vollständig belegt". Das las
                   sich wie „Meldepflicht erfüllt". Hier steht jetzt, was der
                   Fall ist: Es wurde noch nichts abgegeben. -->
              <span v-else-if="!m.nachweis.gemeldet" class="nachweis-badge offen"
                    title="Es wurde noch keine Stufe gemeldet — es gibt noch nichts zu belegen">
                noch nichts gemeldet
              </span>
              <span v-else-if="m.nachweis.vollstaendig" class="nachweis-badge ok"
                    title="Adressaten, Referenzen und Nutzerunterrichtung belegt">
                ✓ belegt
              </span>
              <span v-else-if="m.nachweis.pflicht_offen" class="nachweis-badge fehlt"
                    :title="luckenTitel(m)">
                ⚠ {{ m.nachweis.pflicht_offen }} Pflichtangabe(n) fehlen
              </span>
              <span v-else class="nachweis-badge offen" :title="luckenTitel(m)">
                {{ m.nachweis.offen }} offen
              </span>
            </td>
            <td class="aktionen">
              <button class="btn-link" @click="toggle(m.id)">
                {{ offen === m.id ? 'Schließen' : 'Meldeakte' }}
              </button>
              <a class="btn-link" :href="safeUrl(store.exportUrl(projekt, m.id))" target="_blank">SRP-Export</a>
              <button class="btn-link danger" @click="store.deleteMeldung(projekt, m.id)">🗑</button>
            </td>
          </tr>

          <!-- Meldeakte: Fristen, Adressaten, Nutzerunterrichtung, Lücken -->
          <tr v-if="offen === m.id" class="detail-row">
            <td colspan="6">
              <div class="akte">

                <!-- Fristen -->
                <section class="akte-block">
                  <h4>⏱ Fristen</h4>
                  <ul class="fristen">
                    <li v-for="s in m.deadlines?.stages || []" :key="s.key">
                      <span class="ampel" :class="'ampel-' + s.ampel">{{ ampelWort(s) }}</span>
                      <strong>{{ s.label }}</strong>
                      <span v-if="s.erfuellt_am">
                        — gemeldet {{ kurz(s.erfuellt_am) }}<em v-if="s.verspaetet"> (verspätet)</em>
                      </span>
                      <span v-else-if="s.unbestimmt">— {{ s.hinweis }}</span>
                      <span v-else>
                        — fällig {{ kurz(s.due_at) }}
                        ({{ s.hours_left !== null ? Math.round(s.hours_left) + ' h' : '—' }})
                        <em v-if="s.hinweis"> · {{ s.hinweis }}</em>
                      </span>
                    </li>
                  </ul>

                  <div class="form-row" v-if="m.typ !== 'serious_incident'">
                    <label>Korrektur-/Minderungsmaßnahme verfügbar ab
                      <span class="hint-inline">(Fristbeginn des Abschlussberichts)</span></label>
                    <div class="inline">
                      <input type="datetime-local" v-model="massnahme[m.id]" />
                      <button class="btn-secondary" @click="saveMassnahme(m)">Übernehmen</button>
                    </div>
                  </div>
                  <p v-else class="hint">
                    Abschlussfrist läuft ab Einreichung der 72-Stunden-Meldung
                    <span v-if="m.notification_gemeldet_am">({{ kurz(m.notification_gemeldet_am) }}).</span>
                    <span v-else>— die Meldung ist noch nicht verbucht.</span>
                  </p>
                </section>

                <!-- Adressaten je Stufe -->
                <section class="akte-block">
                  <h4>📨 Gemeldet an — CSIRT-Koordinator und ENISA</h4>
                  <p class="hint">Art. 14 verlangt die Meldung gleichzeitig an den
                    CSIRT-Koordinator des Mitgliedstaats und an die ENISA. Ohne
                    Einreichungsreferenz ist die Meldung im Streitfall nicht auffindbar.</p>

                  <div v-for="stufe in STUFEN" :key="stufe" class="stufe-card">
                    <div class="stufe-head">
                      <strong>{{ stufeLabel(stufe) }}</strong>
                      <span v-if="gemeldetAm(m, stufe)" class="ok">
                        ✓ gemeldet {{ kurz(gemeldetAm(m, stufe)) }}
                      </span>
                      <span v-else class="warn">nicht gemeldet</span>
                    </div>
                    <div class="form-grid">
                      <div class="form-row">
                        <label>Mitgliedstaat des CSIRT-Koordinators *</label>
                        <select v-model="empf(m, stufe).csirt.mitgliedstaat">
                          <option value="">— bitte wählen —</option>
                          <option v-for="(name, code) in store.mitgliedstaaten" :key="code" :value="code">
                            {{ code }} — {{ name }}
                          </option>
                        </select>
                      </div>
                      <div class="form-row">
                        <label>Stelle / CSIRT-Name</label>
                        <input v-model="empf(m, stufe).csirt.stelle" placeholder="z.B. CERT-Bund" />
                      </div>
                      <div class="form-row">
                        <label>Einreichungsreferenz CSIRT *</label>
                        <input v-model="empf(m, stufe).csirt.referenz" placeholder="Vorgangs-/Ticketnummer" />
                      </div>
                      <div class="form-row">
                        <label>Eingangsbestätigung CSIRT</label>
                        <input type="datetime-local" v-model="empf(m, stufe).csirt.eingang_bestaetigt_am" />
                      </div>
                      <div class="form-row">
                        <label>Einreichungsreferenz ENISA *</label>
                        <input v-model="empf(m, stufe).enisa.referenz" placeholder="SRP-Referenz" />
                      </div>
                      <div class="form-row">
                        <label>Eingangsbestätigung ENISA</label>
                        <input type="datetime-local" v-model="empf(m, stufe).enisa.eingang_bestaetigt_am" />
                      </div>
                      <div class="form-row">
                        <label>Gemeldet an CSIRT am</label>
                        <input type="datetime-local" v-model="empf(m, stufe).csirt.gemeldet_am" />
                      </div>
                      <div class="form-row">
                        <label>Gemeldet an ENISA am</label>
                        <input type="datetime-local" v-model="empf(m, stufe).enisa.gemeldet_am" />
                      </div>
                    </div>
                    <div class="inline">
                      <button class="btn-secondary" @click="saveEmpfaenger(m, stufe)">
                        Adressaten speichern
                      </button>
                      <button v-if="!gemeldetAm(m, stufe) && naechsteStufe(m) === stufe"
                              class="btn-primary" @click="melden(m, stufe)">
                        Als gemeldet verbuchen
                      </button>
                    </div>
                    <p v-if="!gemeldetAm(m, stufe) && naechsteStufe(m) !== stufe" class="hint">
                      Zuerst ist {{ stufeLabel(naechsteStufe(m)) }} zu melden.
                    </p>
                  </div>
                </section>

                <!-- Nutzerunterrichtung -->
                <section class="akte-block">
                  <h4>📣 Nutzerunterrichtung (Art. 14 Abs. 8)</h4>
                  <div class="form-grid">
                    <div class="form-row span2">
                      <label>Empfohlene Maßnahmen</label>
                      <textarea v-model="adv(m).empfohlene_massnahmen"></textarea>
                    </div>
                    <div class="form-row">
                      <label>Schweregrad</label>
                      <input v-model="adv(m).schweregrad" placeholder="z.B. hoch" />
                    </div>
                    <div class="form-row">
                      <label>Veröffentlichungskanal *</label>
                      <input v-model="adv(m).veroeffentlichungskanal" placeholder="z.B. Security-Advisory-Seite" />
                    </div>
                    <div class="form-row">
                      <label>URL der Veröffentlichung *</label>
                      <input v-model="adv(m).url" placeholder="https://…" />
                    </div>
                    <div class="form-row">
                      <label>Veröffentlicht am *</label>
                      <input type="datetime-local" v-model="adv(m).veroeffentlicht_am" />
                    </div>
                    <div class="form-row span2">
                      <label>Unterrichteter Empfängerkreis *</label>
                      <input v-model="adv(m).empfaengerkreis"
                             placeholder="z.B. alle Kunden mit Wartungsvertrag (412 Adressaten), öffentliche Advisory-Seite" />
                    </div>
                  </div>
                  <label class="check">
                    <input type="checkbox" v-model="adv(m).veroeffentlicht" />
                    Unterrichtung ist veröffentlicht (Pflichtfelder * werden geprüft)
                  </label>
                  <div class="inline">
                    <button class="btn-primary" @click="saveAdvisory(m)">Speichern</button>
                    <a class="btn-link" :href="safeUrl(csafUrl(m.id))" target="_blank">CSAF-Ausgabe</a>
                  </div>
                </section>

                <!-- Lücken -->
                <section class="akte-block">
                  <h4>🔎 Was die Akte (noch) nicht belegt</h4>
                  <p v-if="!(m.nachweis?.luecken || []).length" class="ok">
                    ✓ Adressaten, Referenzen und Nutzerunterrichtung sind belegt.
                  </p>
                  <ul v-else class="luecken">
                    <li v-for="(l, i) in m.nachweis?.luecken || []" :key="i" :class="l.schwere">
                      <span class="luecke-tag">{{ l.schwere === 'pflicht' ? 'Pflicht' : 'offen' }}</span>
                      {{ l.text }}
                    </li>
                  </ul>
                </section>

              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
    <p v-else class="empty">Noch keine Meldungen erfasst.</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useCraMeldungStore, type Meldung, type MeldungDeadlineStage, type MeldungKanal }
  from '../../stores/craMeldung'
import { safeUrl } from '../../utils/safeUrl'

const props = defineProps<{ projekt: string }>()
const store = useCraMeldungStore()

// Stufen in Melde-Reihenfolge + Abbildung auf den Status-Wert des Backends.
const STUFEN = ['early_warning', 'notification', 'final_report'] as const
const STUFE_STATUS: Record<string, string> = {
  early_warning: 'early_warning_24h',
  notification: 'notification_72h',
  final_report: 'final_report',
}

const showForm = ref(false)
const form = ref({ typ: 'vuln_exploited', titel: '', erkannt_am: '', betroffene_ms: '' })
const offen = ref<number | null>(null)
// Formularzustand je Meldung (Adressaten/Advisory/Maßnahme), damit das Tippen
// nicht direkt den Store-Datensatz verändert.
const empfForm = ref<Record<number, Record<string, Record<string, MeldungKanal>>>>({})
const advForm = ref<Record<number, Record<string, any>>>({})
const massnahme = ref<Record<number, string>>({})

function statusLabel(s: string) {
  return ({
    erkannt: 'Erkannt', early_warning_24h: 'Frühwarnung (24h)',
    notification_72h: 'Meldung (72h)', final_report: 'Abschlussbericht',
  } as Record<string, string>)[s] || s
}

function stufeLabel(s: string) {
  return ({
    early_warning: 'Frühwarnung (24h)', notification: 'Meldung (72h)',
    final_report: 'Abschlussbericht',
  } as Record<string, string>)[s] || s
}

function ampelWort(s: MeldungDeadlineStage) {
  return ({
    gruen: 'grün', gelb: 'gelb', rot: 'rot', overdue: 'überfällig',
    unbestimmt: 'läuft nicht', erfuellt: 'gemeldet', erfuellt_verspaetet: 'verspätet',
  } as Record<string, string>)[s.ampel] || s.ampel
}

function ampelTitle(s: MeldungDeadlineStage) {
  if (s.erfuellt_am) return `${s.label}: gemeldet ${s.erfuellt_am}${s.verspaetet ? ' (verspätet)' : ''}`
  if (s.unbestimmt) return `${s.label}: ${s.hinweis || 'Frist läuft noch nicht'}`
  if (s.overdue) return `${s.label}: überfällig`
  return `${s.label}: fällig ${s.due_at} (${Math.round(s.hours_left || 0)}h)`
}

function kurz(iso?: string | null) {
  return (iso || '').slice(0, 16).replace('T', ' ')
}

/** ISO → Wert für <input type="datetime-local"> (Minutengenauigkeit). */
function fuerInput(iso?: string | null) {
  const s = (iso || '').replace(' ', 'T')
  return s ? s.slice(0, 16) : ''
}

function leererKanal(): MeldungKanal {
  return { mitgliedstaat: '', stelle: '', referenz: '', gemeldet_am: '', eingang_bestaetigt_am: '' }
}

function initForms(m: Meldung) {
  const stufen: Record<string, Record<string, MeldungKanal>> = {}
  for (const st of STUFEN) {
    const q = (m.empfaenger || {})[st] || {}
    stufen[st] = {
      csirt: { ...leererKanal(), ...(q.csirt || {}) },
      enisa: { ...leererKanal(), ...(q.enisa || {}) },
    }
    for (const k of ['csirt', 'enisa'] as const) {
      stufen[st][k].gemeldet_am = fuerInput(stufen[st][k].gemeldet_am)
      stufen[st][k].eingang_bestaetigt_am = fuerInput(stufen[st][k].eingang_bestaetigt_am)
    }
  }
  empfForm.value[m.id] = stufen
  advForm.value[m.id] = {
    empfohlene_massnahmen: '', schweregrad: '', veroeffentlichungskanal: '',
    url: '', empfaengerkreis: '', veroeffentlicht: false,
    ...(m.advisory || {}),
  }
  advForm.value[m.id].veroeffentlicht_am = fuerInput(advForm.value[m.id].veroeffentlicht_am)
  massnahme.value[m.id] = fuerInput(m.massnahme_verfuegbar_ab)
}

function empf(m: Meldung, stufe: string) {
  if (!empfForm.value[m.id]) initForms(m)
  return empfForm.value[m.id][stufe]
}

function adv(m: Meldung) {
  if (!advForm.value[m.id]) initForms(m)
  return advForm.value[m.id]
}

function gemeldetAm(m: Meldung, stufe: string): string {
  return (m as any)[`${stufe}_gemeldet_am`] || ''
}

/** Die nächste zu meldende Stufe (nur vorwärts, wie im Backend). */
function naechsteStufe(m: Meldung): string {
  for (const st of STUFEN) if (!gemeldetAm(m, st)) return st
  return ''
}

function luckenTitel(m: Meldung) {
  return (m.nachweis?.luecken || []).map(l => l.text).join('\n')
}

function csafUrl(id: number) {
  return `/api/cra-meldung/projekte/${encodeURIComponent(props.projekt)}`
    + `/meldungen/${id}/nutzer-advisory/csaf`
}

function toggle(id: number) {
  if (offen.value === id) { offen.value = null; return }
  const m = store.meldungen.find(x => x.id === id)
  if (m) initForms(m)
  offen.value = id
}

async function create() {
  await store.createMeldung(props.projekt, { ...form.value })
  showForm.value = false
  form.value = { typ: 'vuln_exploited', titel: '', erkannt_am: '', betroffene_ms: '' }
}

async function saveEmpfaenger(m: Meldung, stufe: string) {
  const ok = await store.saveEmpfaenger(props.projekt, m.id, stufe, empf(m, stufe))
  if (ok) nachladen(m.id)
}

async function melden(m: Meldung, stufe: string) {
  const ok = await store.setStufe(props.projekt, m.id, STUFE_STATUS[stufe], empf(m, stufe))
  if (ok) nachladen(m.id)
}

async function saveMassnahme(m: Meldung) {
  const ok = await store.updateMeldung(props.projekt, m.id,
    { massnahme_verfuegbar_ab: massnahme.value[m.id] || '' })
  if (ok) nachladen(m.id)
}

async function saveAdvisory(m: Meldung) {
  const ok = await store.saveAdvisory(props.projekt, m.id, adv(m))
  if (ok) nachladen(m.id)
}

/** Nach dem Speichern die Formulare aus dem neu geladenen Datensatz auffüllen. */
function nachladen(id: number) {
  const m = store.meldungen.find(x => x.id === id)
  if (m) initForms(m)
}

function load() {
  if (props.projekt) store.fetchMeldungen(props.projekt)
}

onMounted(() => { store.fetchConstants(); load() })
watch(() => props.projekt, () => { offen.value = null; load() })
</script>

<style scoped>
.panel-header h3 { color: #1565c0; margin-bottom: 4px; }
.panel-header .sub { color: #607d8b; font-size: 13px; }
.form-card { background: #f5f8fc; border: 1px solid #cfd8e3; border-radius: 8px; padding: 16px; margin: 12px 0; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; }
.form-row { display: flex; flex-direction: column; margin-bottom: 8px; }
.form-row.span2 { grid-column: span 2; }
.form-row label { font-size: 12px; color: #455a64; margin-bottom: 2px; }
.hint-inline { color: #90a4ae; font-weight: normal; }
.meldung-table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 12px; }
.meldung-table th, .meldung-table td { border-bottom: 1px solid #e0e0e0; padding: 6px 8px; text-align: left; vertical-align: top; }
.aktionen { white-space: nowrap; }
.ampel { display: inline-block; padding: 1px 6px; margin: 1px; border-radius: 4px; font-size: 11px; color: #fff; }
.ampel-gruen { background: #2e7d32; }
.ampel-gelb { background: #f9a825; color: #000; }
.ampel-rot { background: #e53935; }
.ampel-overdue { background: #b71c1c; }
.ampel-unbestimmt { background: #eceff1; color: #546e7a; border: 1px solid #cfd8e3; }
.ampel-erfuellt { background: #1565c0; }
.ampel-erfuellt_verspaetet { background: #ef6c00; }
.nachweis-badge { display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 11px; }
.nachweis-badge.ok { background: #e8f5e9; color: #2e7d32; }
.nachweis-badge.fehlt { background: #ffebee; color: #c62828; }
.nachweis-badge.offen { background: #fff8e1; color: #ef6c00; }
.detail-row > td { background: #fafcff; }
.akte-block { margin-bottom: 18px; }
.akte-block h4 { color: #1565c0; font-size: 14px; margin: 0 0 6px; }
.fristen { list-style: none; padding: 0; margin: 0 0 10px; font-size: 13px; }
.fristen li { padding: 2px 0; }
.stufe-card { border: 1px solid #cfd8e3; border-radius: 8px; padding: 12px; margin-bottom: 10px; background: #fff; }
.stufe-head { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; }
.inline { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.check { display: block; font-size: 13px; color: #455a64; margin: 6px 0 10px; }
.luecken { list-style: none; padding: 0; margin: 0; font-size: 13px; }
.luecken li { padding: 3px 0; }
.luecke-tag { display: inline-block; min-width: 54px; padding: 1px 6px; margin-right: 6px; border-radius: 4px; font-size: 11px; text-align: center; }
.luecken li.pflicht .luecke-tag { background: #ffebee; color: #c62828; }
.luecken li.offen .luecke-tag { background: #fff8e1; color: #ef6c00; }
.ok { color: #2e7d32; font-size: 12px; }
.warn { color: #ef6c00; font-size: 12px; }
.hint { color: #90a4ae; font-size: 12px; margin: 4px 0; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; padding: 0 4px; }
.btn-link.danger { color: #c62828; }
.empty { color: #90a4ae; font-style: italic; }
</style>
