<template>
  <div class="conf-panel">
    <p v-if="!projekt" class="hint">{{ $t('common.bitteZuerstEinAIActProjektAu') }}</p>

    <template v-else-if="rec">
      <div class="conf-toolbar">
        <div class="toolbar-info">
          <strong>{{ $t('aiact.conformityPanel.artKonformitatsbewertungCEKennzeichn') }}</strong>
          <span class="muted">{{ $t('aiact.conformityPanel.ergebnisV0', { v0: rec.ergebnis }) }}</span>
        </div>
      </div>

      <!-- DoC-Gate-Status -->
      <div class="gate" :class="store.docGate?.doc_allowed ? 'gate-ok' : 'gate-blocked'" v-if="store.docGate">
        <strong v-if="store.docGate.doc_allowed">{{ $t('aiact.conformityPanel.doCAusstellbarBewertungswegAbgeschlo') }}</strong>
        <strong v-else-if="store.docGate.reassessment_required">{{ $t('aiact.conformityPanel.reAssessmentNotigWesentlicheAnderung') }}</strong>
        <strong v-else>{{ $t('aiact.conformityPanel.doCGesperrtBewertungswegNichtAbgesch') }}</strong>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>

      <!-- #1889: Die EU-Konformitätserklärung nach Art. 47 i.V.m. Anhang V.
           Sie existierte bis v8.2.3 nur als Prompt — kein Datensatz, kein
           Ausstellen, kein Archiv, obwohl Art. 47 Abs. 2 zehn Jahre
           Bereithaltung verlangt. -->
      <KonformitaetserklaerungForm ref="docForm" :projekt="projekt"
                                   @ausgestellt="load"
                                   @assistent="docAssistentOffen = true" />

      <!-- #1889: Der Assistent kann sein Ergebnis jetzt in das Formular
           übernehmen — und zwar nur die Prosafelder, die der Server freigibt. -->
      <DocAssistentModal v-if="docAssistentOffen" :projekt="projekt"
                         @uebernehmen="(f: any) => docForm?.uebernehmeAusKi(f)"
                         @close="docAssistentOffen = false" />

      <section class="card">
        <h4>{{ $t('aiact.conformityPanel.verfahrensweg') }}</h4>
        <label class="full">
          <select v-model="rec.verfahren">
            <option v-for="v in store.verfahren" :key="v.code" :value="v.code">{{ v.label }}</option>
          </select>
        </label>
        <label class="inline">{{ $t('common.ergebnis') }}
          <select v-model="rec.ergebnis">
            <option v-for="e in ergebnisWerte" :key="e" :value="e">{{ e }}</option>
          </select>
        </label>
        <label class="inline">{{ $t('aiact.conformityPanel.bewertungsdatum') }}<input type="date" v-model="rec.bewertungsdatum" /></label>
      </section>

      <!-- Annex VI: interne Kontrolle -->
      <section class="card" v-if="rec.verfahren === 'annex_vi_intern'">
        <h4>{{ $t('aiact.conformityPanel.annexVISelbstprufungInterneKontrolle') }}</h4>
        <label class="check"><input type="checkbox" v-model="rec.qms_geprueft" /> {{ $t('aiact.conformityPanel.qMSGepruftArt') }}</label>
        <label class="check"><input type="checkbox" v-model="rec.techdoc_geprueft" /> {{ $t('aiact.conformityPanel.technischeDokuAnnexIVGepruftArt') }}</label>
        <div class="checklist">
          <label class="check" v-for="c in store.checkliste" :key="c.key">
            <input type="checkbox" :checked="!!rec.checkliste[c.key]"
                   @change="rec.checkliste[c.key] = ($event.target as HTMLInputElement).checked" />
            {{ c.label }}
          </label>
        </div>
      </section>

      <!-- Annex VII: notifizierte Stelle -->
      <section class="card" v-else>
        <h4>{{ $t('aiact.conformityPanel.annexVIIPfadNotifizierteStelle') }}</h4>
        <div class="grid">
          <label>{{ $t('aiact.conformityPanel.nBName') }}<input v-model="rec.notified_body_name" /></label>
          <label>{{ $t('aiact.conformityPanel.nBKennnummer') }}<input v-model="rec.notified_body_kennnummer" placeholder="4-stellig" /></label>
        </div>
        <div class="row">
          <input type="file" accept="application/pdf" @change="onCert" />
          <span class="muted" v-if="rec.nb_zertifikat_sha256">
            {{ $t('aiact.conformityPanel.zertifikatSHAV0', { v0: rec.nb_zertifikat_sha256.slice(0, 12) }) }}
          </span>
        </div>
      </section>

      <!-- CE + Re-Assessment -->
      <section class="card">
        <h4>{{ $t('aiact.conformityPanel.cEKennzeichnungWesentlicheAnderung') }}</h4>
        <div class="grid">
          <label>{{ $t('aiact.conformityPanel.cEAngebrachtAm') }}<input type="date" v-model="rec.ce_angebracht_am" /></label>
          <label>{{ $t('aiact.conformityPanel.wesentlicheAnderungSeit') }}<input type="date" v-model="rec.wesentliche_aenderung_seit" /></label>
        </div>
        <p class="muted">{{ $t('aiact.conformityPanel.eineWesentlicheAnderungNachDemBewert') }}</p>
      </section>

      <div class="row">
        <button class="btn-primary" :disabled="busy" @click="save">{{ $t('common.saveIcon') }}</button>
      </div>

      <!-- #1243: Optionale CRA-Verknüpfung -->
      <section class="card cra-link">
        <h4>{{ $t('aiact.conformityPanel.optionaleCRAVerknupfungArt') }}</h4>
        <p class="muted">
          <strong>{{ $t('aiact.conformityPanel.optionalUndManuell') }}</strong> {{ $t('aiact.conformityPanel.falltDasKISystemZugleichAlsProduktMi') }} <strong>{{ $t('aiact.conformityPanel.nichtErforderlich') }}</strong> {{ $t('aiact.conformityPanel.dieBewertungKannVollstandigManuellEr') }}
        </p>
        <div class="grid">
          <label>{{ $t('aiact.conformityPanel.cRAProjektVerknupfen') }}
            <select v-model="craSel">
              <option value="">{{ $t('aiact.conformityPanel.keineVerknupfungManuell') }}</option>
              <option v-for="p in store.craItems" :key="p.name" :value="p.name">
                {{ p.produkt_match ? '★ ' : '' }}{{ p.name }}{{ !p.firma_match && p.unternehmen ? ` (${p.unternehmen})` : '' }}
              </option>
            </select>
            <small v-if="!store.craItems.length" class="muted">{{ $t('aiact.conformityPanel.keineCRAProjekteVorhanden') }}</small>
            <small v-else-if="store.craVorschlag && !store.craLink?.linked_cra_projekt" class="muted">
              {{ $t('aiact.conformityPanel.vorschlagV0GleichesProdukt', { v0: store.craVorschlag }) }}
            </small>
          </label>
          <label class="check"><input type="checkbox" v-model="craOverride" /> {{ $t('aiact.conformityPanel.manuellUberstimmenCRADatenIgnorieren') }}</label>
        </div>
        <div class="row">
          <button class="btn-secondary" :disabled="busy" @click="saveCraLink">{{ $t('aiact.conformityPanel.verknupfungSpeichern') }}</button>
          <button class="btn-link" v-if="store.craLink?.linked_cra_projekt" :disabled="busy" @click="clearCraLink">{{ $t('aiact.conformityPanel.verknupfungLosen') }}</button>
        </div>
        <div v-if="store.craLink?.linked && store.craLink?.cra_record" class="cra-readonly">
          <strong>{{ $t('aiact.conformityPanel.readOnlyAusCRAProjektV0', { v0: store.craLink.linked_cra_projekt }) }}</strong>
          <ul>
            <li>{{ $t('aiact.conformityPanel.cEStatusV0', { v0: store.craLink.cra_record.ce_status || '—' }) }}</li>
            <li>{{ $t('aiact.conformityPanel.bewertungswegV0', { v0: store.craLink.cra_record.bewertungsweg || '—' }) }}</li>
            <li>{{ $t('aiact.conformityPanel.nBKennnummerV0', { v0: store.craLink.cra_record.nb_kennnummer || '—' }) }}</li>
            <li>{{ $t('aiact.conformityPanel.bewertungAbgeschlossenV0', { v0: store.craLink.cra_record.bewertung_abgeschlossen ? 'ja' : 'nein' }) }}</li>
          </ul>
        </div>
        <p v-else-if="store.craLink?.manual_override" class="muted">
          {{ $t('aiact.conformityPanel.manuellUberstimmtCRADatenWerdenNicht') }}
        </p>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import { useAiactConformityStore, type ConformityRecord } from '../../stores/aiactConformity'
import KonformitaetserklaerungForm from '../../components/aiact/KonformitaetserklaerungForm.vue'
import DocAssistentModal from '../../components/aiact/DocAssistentModal.vue'
import { t } from '../../i18n'

const aiact = useAiActStore()
const store = useAiactConformityStore()

const projekt = computed(() => aiact.selectedProjekt)
const rec = ref<ConformityRecord | null>(null)
const busy = ref(false)
const message = ref('')

const ergebnisWerte = computed(() => store.ergebnisWerte.length ? store.ergebnisWerte
  : ['offen', 'konform', 'nicht_konform'])

// #1889: Der A8-Assistent schreibt jetzt in die Erklärungsmaske.
const docAssistentOffen = ref(false)
const docForm = ref<any>(null)

const craSel = ref('')
const craOverride = ref(false)

async function load() {
  if (!projekt.value) return
  await store.loadConstants()
  await store.load(projekt.value)
  rec.value = store.record ? { ...store.record, checkliste: { ...(store.record.checkliste || {}) } } : null
  // #1243: CRA-Verknüpfung laden (optional, read-only Referenz).
  await store.loadCraLink(projekt.value)
  await store.loadCraProjekte(projekt.value)
  craSel.value = store.craLink?.linked_cra_projekt || ''
  craOverride.value = !!store.craLink?.manual_override
}

async function saveCraLink() {
  if (!projekt.value) return
  busy.value = true
  try {
    await store.setCraLink(projekt.value, { linked_cra_projekt: craSel.value, manual_override: craOverride.value })
    message.value = t('aiact.conformityPanel.cRAVerknupfungGespeichert')
  } finally { busy.value = false }
}

async function clearCraLink() {
  if (!projekt.value) return
  busy.value = true
  try {
    await store.setCraLink(projekt.value, { linked_cra_projekt: '', manual_override: false })
    craSel.value = ''
    craOverride.value = false
    message.value = t('aiact.conformityPanel.cRAVerknupfungGelost')
  } finally { busy.value = false }
}

async function save() {
  if (!projekt.value || !rec.value) return
  busy.value = true
  try {
    await store.save(projekt.value, rec.value)
    rec.value = store.record ? { ...store.record, checkliste: { ...(store.record.checkliste || {}) } } : rec.value
    message.value = t('aiact.conformityPanel.konformitatsbewertungGespeichert')
  } catch (e: any) {
    message.value = e?.response?.data?.error || t('common.speichernFehlgeschlagen')
  } finally { busy.value = false }
}

async function onCert(e: Event) {
  if (!projekt.value) return
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    await store.uploadCertificate(projekt.value, file)
    rec.value = store.record ? { ...store.record, checkliste: { ...(store.record.checkliste || {}) } } : rec.value
    message.value = 'Zertifikat hochgeladen.'
  } catch (err: any) {
    message.value = err?.response?.data?.error || t('aiact.conformityPanel.uploadFehlgeschlagen')
  }
}

watch(projekt, load, { immediate: true })
</script>

<style scoped>
.conf-panel { padding: 8px 0; }
.hint { color: #607d8b; padding: 16px; }
.conf-toolbar { background: #1565c0; color: #fff; padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; }
.toolbar-info strong { color: #fff; }
.toolbar-info .muted { color: #90caf9; margin-left: 12px; }
.gate { padding: 10px 14px; border-radius: 8px; margin-bottom: 12px; }
.gate-ok { background: #e8f5e9; border: 1px solid #a5d6a7; }
.gate-blocked { background: #fff3e0; border: 1px solid #ffcc80; }
.status-msg { color: #1565c0; margin: 8px 0; }
.card { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.card h4 { margin: 0 0 8px; color: #0d47a1; }
label { display: flex; flex-direction: column; font-size: 0.85em; color: #455a64; gap: 3px; }
label.full { width: 100%; }
label.inline { display: inline-flex; margin-right: 16px; margin-top: 8px; }
label.check { flex-direction: row; align-items: center; gap: 8px; margin: 6px 0; }
.grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.checklist { margin-top: 8px; border-top: 1px solid #eee; padding-top: 8px; }
input, select { box-sizing: border-box; padding: 4px 6px; }
select { width: 100%; }
.row { display: flex; gap: 12px; align-items: center; margin-top: 8px; }
.muted { color: #78909c; font-size: 0.85em; }
.btn-secondary { background: #eceff1; border: 1px solid #cfd8dc; border-radius: 4px; padding: 6px 12px; cursor: pointer; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; text-decoration: underline; }
.cra-link { border-left: 4px solid #7b1fa2; }
.cra-link h4 { color: #4a148c; }
.cra-readonly { background: #f3e5f5; border-radius: 6px; padding: 10px 14px; margin-top: 8px; font-size: 0.88em; }
.cra-readonly ul { margin: 6px 0 0; padding-left: 18px; }
</style>
