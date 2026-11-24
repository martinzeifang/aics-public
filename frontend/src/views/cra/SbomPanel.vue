<template>
  <div class="sbom-panel">
    <div class="info-banner">
      <h3>{{ $t('cra.pflichtDokuPanel.c1SBOMVerzeichnis') }}</h3>
      <p>
        {{ $t('cra.sbomPanel.einleitung') }}
        <button class="btn-link zurueck" @click="emit('zurueck')">← {{ $t('cra.sbomPanel.zurDokumentation') }}</button>
      </p>
    </div>

    <div class="section-full">
        <div class="form-grid">
          <input v-model="sbomForm.release_version" :placeholder="$t('cra.sbomPanel.phReleaseVersion')" />
          <!-- #1771: Ein Produkt besteht oft aus mehreren Artefakten. Ohne
               Benennung kollidieren zwei SBOMs derselben Version. -->
          <input v-model="sbomForm.artefakt" :placeholder="$t('cra.pflichtDokuPanel.artefaktZBAnwendungWebserver')" />
          <select v-model="sbomForm.sbom_format">
            <option value="spdx">{{ $t('cra.pflichtDokuPanel.sPDX') }}</option>
            <option value="cyclonedx">{{ $t('cra.pflichtDokuPanel.cycloneDX') }}</option>
          </select>
          <input v-model.number="sbomForm.komponenten_count" type="number" :placeholder="$t('cra.pflichtDokuPanel.komponentenAnzahl')" />
          <input v-model="sbomForm.quelle" :placeholder="$t('cra.pflichtDokuPanel.quelleZBCiArtifactGhRun')" />
          <input v-model="sbomForm.blob_path" :placeholder="$t('cra.pflichtDokuPanel.pfadZurSBOMDatei')" />
          <input v-model="sbomLizenzenInput" :placeholder="$t('cra.pflichtDokuPanel.lizenzenKommaGetrenntMITApache')" />
          <button class="btn-primary" @click="addSbom">{{ $t('cra.pflichtDokuPanel.sBOMHinzufugen') }}</button>
        </div>
        <!-- #1769: Was an der richtigen Stelle liegt, soll die Anwendung
             selbst finden. Format, Anzahl, Lizenzen und die Komponentenliste
             kommen dann aus der Datei statt aus dem Formular darüber. -->
        <div class="sbom-einlesen">
          <button class="btn-mini" :disabled="einlesenBusy" @click="sbomEinlesen">
            {{ einlesenBusy ? $t('common.liestEin') : $t('cra.pflichtDokuPanel.ausAblageortEinlesen') }}</button>
          <span class="hint-klein">
            {{ $t('cra.pflichtDokuPanel.dateienUnter') }} <code>data/cra/sbom/{{ projektOrdner }}/*.json</code>
            {{ $t('cra.pflichtDokuPanel.cycloneDXOderSPDXWerdenGelesenUndAng') }}
          </span>
          <span v-if="einlesenMeldung" class="einlesen-meldung">{{ einlesenMeldung }}</span>
        </div>
        <!-- #2062 -->
        <div class="tabelle-scroll">
        <table class="sbom-table">
          <thead><tr><th>{{ $t('cra.pflichtDokuPanel.release') }}</th><th>{{ $t('cra.pflichtDokuPanel.artefakt') }}</th><th>{{ $t('common.format') }}</th><th>{{ $t('cra.pflichtDokuPanel.komp') }}</th><th>{{ $t('common.date') }}</th><th>{{ $t('cra.pflichtDokuPanel.sBOM') }}</th><th>{{ $t('common.quelle') }}</th><th>{{ $t('cra.pflichtDokuPanel.komponenten') }}</th><th></th></tr></thead>
          <tbody>
            <template v-for="s in store.sboms" :key="s.id">
            <tr>
              <td>{{ s.release_version }}</td>
              <td>{{ s.artefakt || '—' }}</td>
              <td>{{ s.sbom_format }}</td>
              <td>{{ s.komponenten_count }}</td>
              <td>{{ (s.sbom_datum || '').slice(0,10) }}</td>
              <td>
                <!-- #1422: externe Adresse direkt verlinken.
                     #1823: liegt die SBOM am Image oder im Ablageort, holt sie
                     der Server — vorher stand hier „—", und das Dokument war
                     über die Oberfläche gar nicht zu bekommen. -->
                <a v-if="sbomLink(s)" :href="sbomLink(s)" target="_blank" rel="noopener" class="sbom-dl">{{ $t('cra.pflichtDokuPanel.abrufen') }}</a>
                <button v-else-if="s.blob_path" class="btn-link sbom-dl"
                        :disabled="dlBusy === s.id" @click="sbomHerunterladen(s)"
                        :title="`SBOM zu ${s.blob_path} herunterladen`">
                  {{ dlBusy === s.id ? $t('cra.pflichtDokuPanel.ladt') : $t('cra.pflichtDokuPanel.herunterladen') }}</button>
                <span v-else class="muted">—</span>
              </td>
              <td>{{ s.quelle }}</td>
              <td>
                <!-- #1761: Die Komponentenliste ist der Inhalt der SBOM. Ohne
                     sie ist die Sorgfaltspflicht (Art. 13 Abs. 5) nicht
                     belegbar — der Hinweis sagt das, statt es zu verschweigen. -->
                <button class="btn-mini" @click="toggleKomponenten(s)">
                  {{ $t('cra.pflichtDokuPanel.v0ListeAmpVergleich', { v0: offeneSbom === s.id ? '▾' : '▸' }) }}</button>
                <!-- #1761: `liste_anzahl` kommt mit der SBOM-Liste vom Server.
                     Vorher stand hier der lazy geladene Store — der ist vor dem
                     Aufklappen leer, und die Warnung behauptete „keine Liste",
                     wo eine existierte. Ein falsches „nicht belegbar" ist so
                     schlimm wie ein falsches „belegt". -->
                <span v-if="!komponentenVorhanden(s)"
                      class="komp-warn" :title="$t('cra.pflichtDokuPanel.artAbsOhneKomponentenlisteNichtBeleg')">
                  {{ $t('cra.pflichtDokuPanel.keineListe') }}</span>
                <span v-else class="komp-ok">{{ $t('cra.pflichtDokuPanel.v0Komponenten', { v0: komponentenAnzahl(s) }) }}</span>
              </td>
              <td><button class="btn-link" @click="store.deleteSbom(s.id)">🗑️</button></td>
            </tr>
            <tr v-if="offeneSbom === s.id" class="komp-row">
              <td colspan="9">
                <div class="komp-import">
                  <label>{{ $t('cra.pflichtDokuPanel.sBOMDateiCycloneDXOderSPDXJSONEinles') }}
                    <input type="file" accept=".json,application/json" @change="sbomDatei(s, $event)" />
                  </label>
                  <span v-if="kompBusy" class="muted">{{ $t('cra.pflichtDokuPanel.liest') }}</span>
                  <span v-if="kompMeldung" class="komp-meldung">{{ kompMeldung }}</span>
                </div>
                <!-- #1770: Container-Produkte liefern die SBOM nicht als Datei,
                     sondern als signierte Attestation am Image. Steht im Feld
                     „Pfad zur SBOM-Datei" eine Image-Referenz, holt die
                     Anwendung sie selbst. -->
                <div v-if="istImageRef(s)" class="komp-import">
                  <button class="btn-mini" :disabled="registryBusy === s.id"
                          @click="ausRegistry(s)">
                    {{ registryBusy === s.id ? '… holt' : $t('cra.pflichtDokuPanel.sBOMVomImageHolen') }}</button>
                  <span class="hint-klein">
                    {{ $t('cra.pflichtDokuPanel.attestationZu') }} <code>{{ s.blob_path }}</code> {{ $t('cra.pflichtDokuPanel.ausDerRegistryNurRegistriesAusDerPos') }}
                  </span>
                  <span v-if="registryMeldung[String(s.id)]" class="komp-meldung">
                    {{ registryMeldung[String(s.id)] }}</span>
                </div>

                <!-- Gerechneter Befund: neu / angehoben / entfallen -->
                <div v-if="befundFuer(s)" class="komp-befund">
                  <strong>{{ $t('cra.pflichtDokuPanel.vergleich') }}</strong>
                  <span v-if="befundFuer(s).erstbewertung" class="muted">
                    {{ $t('cra.pflichtDokuPanel.erstReleaseOhneVorgangerJedeKomponen') }}</span>
                  <span v-else class="muted">
                    gegen {{ befundFuer(s).vorgaenger_version || '—' }}</span>
                  <span class="komp-pill neu">neu {{ (befundFuer(s).vergleich?.neu || []).length }}</span>
                  <span class="komp-pill hoch">angehoben {{ (befundFuer(s).vergleich?.angehoben || []).length }}</span>
                  <span class="komp-pill weg">entfallen {{ (befundFuer(s).vergleich?.entfallen || []).length }}</span>
                  <span class="komp-pill">{{ $t('cra.pflichtDokuPanel.unverandertV0', { v0: befundFuer(s).vergleich?.unveraendert || 0 }) }}</span>
                  <span class="komp-pill" :class="{ offen: (befundFuer(s).unbewertet || []).length }">
                    {{ befundFuer(s).bewertet || 0 }}/{{ befundFuer(s).pflichtig || 0 }} bewertet</span>
                </div>

                <div v-if="(store.sbomKomponenten[String(s.id)] || []).length" class="komp-bewertung">
                  <select v-model="kompStatus">
                    <option value="geprueft">{{ $t('cra.pflichtDokuPanel.gepruft') }}</option>
                    <option value="nicht_relevant">{{ $t('cra.pflichtDokuPanel.nichtRelevant') }}</option>
                    <option value="offen">{{ $t('cra.pflichtDokuPanel.zurucksetzenOffen') }}</option>
                  </select>
                  <input v-model="kompNotiz" class="komp-notiz"
                         :placeholder="$t('cra.pflichtDokuPanel.begrundungMindZeichenWasWurdeGepruft')" />
                  <button class="btn-primary" :disabled="!kompAuswahl.length || kompBusy"
                          @click="bewerteAuswahl(s)">
                    {{ kompAuswahl.length }} Komponente(n) bewerten</button>
                  <button class="btn-link" @click="auswahlPflichtig(s)">
                    {{ $t('cra.pflichtDokuPanel.auswahlAlleNeuenAngehobenen') }}</button>
                  <button class="btn-link" @click="kompAuswahl = []">{{ $t('cra.pflichtDokuPanel.auswahlLeeren') }}</button>
                  <!-- #1773: Der Weg für den Regelfall. 184 Komponenten einzeln
                       zu begründen ist die Stelle, an der ein Prüfpunkt
                       umgangen statt beantwortet wird. -->
                  <button class="btn-mini" @click="klassenFuer = s">
                    {{ $t('cra.pflichtDokuPanel.nachKlassenBewerten') }}</button>
                </div>

                <table class="komp-table" v-if="(store.sbomKomponenten[String(s.id)] || []).length">
                  <thead><tr><th></th><th>{{ $t('cra.pflichtDokuPanel.komponente') }}</th><th>{{ $t('common.version') }}</th><th>{{ $t('cra.pflichtDokuPanel.lieferant') }}</th>
                    <th>{{ $t('license.title') }}</th><th>{{ $t('cra.pflichtDokuPanel.befunde') }}</th><th>{{ $t('common.bewertung') }}</th></tr></thead>
                  <tbody>
                    <tr v-for="k in (store.sbomKomponenten[String(s.id)] || [])" :key="k.id"
                        :class="{ 'komp-neu': istPflichtig(s, k) }">
                      <td><input type="checkbox" :value="k.id" v-model="kompAuswahl" /></td>
                      <td :title="k.purl || ''">{{ k.name }}
                        <span v-if="istPflichtig(s, k)" class="komp-pill neu">{{ $t('cra.pflichtDokuPanel.neuAngehoben') }}</span>
                      </td>
                      <td>{{ k.version || '—' }}</td>
                      <td>{{ k.lieferant || '—' }}</td>
                      <td>{{ k.lizenz || '—' }}</td>
                      <!-- #1774: Beides lag in der Anwendung, nur nicht an
                           derselben Stelle — wer hier bewertete, musste den
                           Befund im C3-Reiter nachsehen. -->
                      <td :title="befundTitel(k)">
                        <span v-if="k.befunde_offen" class="komp-pill weg">
                          🛡️ {{ k.befunde_offen }} offen</span>
                        <span v-else-if="(k.befunde || []).length" class="komp-pill geprueft">
                          🛡️ {{ k.befunde.length }} behandelt</span>
                        <span v-else class="muted">—</span>
                      </td>
                      <td :title="k.bewertung_notiz || ''">
                        <span class="komp-pill" :class="k.bewertung_status">
                          {{ KOMP_LABEL[k.bewertung_status] || k.bewertung_status }}</span>
                        <span v-if="k.bewertet_von" class="muted"> · {{ k.bewertet_von }}</span>
                        <!-- Widerspruch in der eigenen Akte: „berührt die
                             Sicherheitseigenschaften nicht" trotz offenem Befund. -->
                        <span v-if="k.befunde_offen && k.bewertung_status === 'nicht_relevant'"
                              class="komp-warn"
                              :title="$t('cra.pflichtDokuPanel.derOffeneBefundBelegtDasGegenteilBew')">
                          {{ $t('cra.pflichtDokuPanel.widerspruch') }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </td>
            </tr>
            </template>
          </tbody>
        </table>
        </div>
    </div>

    <!-- #1773: Fremdkomponenten nach Klassen bewerten, mit KI-Entwurf je Gruppe -->
    <KomponentenKlassenModal v-if="klassenFuer"
                             :sbom-id="klassenFuer.id"
                             :version="klassenFuer.release_version"
                             :artefakt="klassenFuer.artefakt"
                             @close="klassenFuer = null"
                             @geaendert="nachKlassenBewertung" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useCraStore } from '../../stores/cra'
import KomponentenKlassenModal from '../../components/cra/KomponentenKlassenModal.vue'
import { t } from '../../i18n'

const store = useCraStore()

const emit = defineEmits<{
  /** Bittet den Host (CRAView), zurück zur Dokumentation zu wechseln. */
  (e: 'zurueck'): void
}>()

const sbomForm = ref({ release_version: '', artefakt: '', sbom_format: 'spdx', komponenten_count: 0, quelle: '', blob_path: '' })
// #1422: SBOM als Link abrufbar — blob_path ist i.d.R. eine URL (Release-Asset /
// Actions-Run / Workflow-Datei aus dem Autodetect). Nur http(s) verlinken.
const sbomLink = (s: any): string => {
  const p = String(s?.blob_path || '').trim()
  return /^https?:\/\//i.test(p) ? p : ''
}
const sbomLizenzenInput = ref('')

// #1823: Download für SBOMs, die nicht unter einer http-Adresse liegen —
// Attestation am Image oder Datei im Ablageort. Den Weg kennt der Server.
const dlBusy = ref<number | null>(null)
const sbomHerunterladen = async (s: any) => {
  dlBusy.value = s.id
  try { await store.sbomHerunterladen(s) } finally { dlBusy.value = null }
}

// #1770: SBOM-Attestation am Image holen.
const registryBusy = ref<number | null>(null)
const registryMeldung = ref<Record<string, string>>({})
/** Sieht der Pfad nach einer Image-Referenz aus (und nicht nach einer URL)? */
const istImageRef = (s: any): boolean => {
  const p = String(s?.blob_path || '').trim()
  if (!p || /^https?:\/\//i.test(p) || p.startsWith('/')) return false
  return /^[a-z0-9.\-]+(:\d+)?\/[a-z0-9._\-/]+(:[\w][\w.\-]*)?(@sha256:[0-9a-f]{64})?$/i.test(p)
}
const ausRegistry = async (s: any) => {
  registryBusy.value = s.id
  registryMeldung.value = { ...registryMeldung.value, [String(s.id)]: '' }
  try {
    const d = await store.sbomAusRegistry(s.id)
    registryMeldung.value = {
      ...registryMeldung.value,
      [String(s.id)]: d
        ? `${d.komponenten} Komponenten aus der Attestation (${d.digest?.slice(0, 19)}…)`
          + (d.zusammengefasst ? ` · ${d.zusammengefasst} Mehrfachnennung(en) zusammengefasst` : '')
        : (store.error || t('cra.pflichtDokuPanel.attestationNichtAbrufbar')),
    }
  } finally {
    registryBusy.value = null
  }
}

// #1769: SBOMs aus dem Ablageort übernehmen.
const einlesenBusy = ref(false)
const einlesenMeldung = ref('')
const projektOrdner = computed(() =>
  String(store.selectedProjekt || '').replace(/[\\/:*?"<>|]/g, '-').replace(/\s+/g, '_'))

const sbomEinlesen = async () => {
  einlesenBusy.value = true
  einlesenMeldung.value = ''
  try {
    const data = await store.einleseSboms()
    if (!data) { einlesenMeldung.value = store.error || 'Einlesen fehlgeschlagen'; return }
    const n = (data.angelegt || []).length
    if (!data.gefunden) {
      einlesenMeldung.value = `Nichts gefunden unter ${data.ablageort}/${projektOrdner.value}/`
    } else if (!n) {
      einlesenMeldung.value =
        `${data.gefunden} Datei(en) gefunden — alle bereits erfasst (${(data.uebersprungen || []).join(', ')}).`
    } else {
      const liste = (data.angelegt || [])
        .map((a: any) => `${a.release_version} (${a.komponenten} Komponenten)`).join(', ')
      einlesenMeldung.value = `${n} SBOM(s) übernommen: ${liste}`
    }
  } catch (e: any) {
    einlesenMeldung.value = e?.response?.data?.error || 'Einlesen fehlgeschlagen'
  } finally {
    einlesenBusy.value = false
  }
}

const addSbom = async () => {
  const payload = {
    ...sbomForm.value,
    lizenzen: sbomLizenzenInput.value.split(',').map(s => s.trim()).filter(Boolean),
  }
  const ok = await store.saveSbom(payload)
  if (ok) {
    sbomForm.value = { release_version: '', artefakt: '', sbom_format: 'spdx', komponenten_count: 0, quelle: '', blob_path: '' }
    sbomLizenzenInput.value = ''
    await store.fetchPflichtDokuStatus()
  }
}

// ── #1761: Komponentenliste je SBOM (Art. 13 Abs. 5) ───────────────────────
// Die Bewertung hängt an der **Komponente**, nicht am Release: Die
// Sorgfaltspflicht ist eine Aussage über eine bestimmte Abhängigkeit. Erst
// dadurch ist der Release-Prüfpunkt gerechnet statt behauptet.

const KOMP_LABEL: Record<string, string> = {
  offen: 'offen', geprueft: 'geprüft', nicht_relevant: 'nicht relevant',
}
const offeneSbom = ref<number | null>(null)
const kompAuswahl = ref<number[]>([])
const kompStatus = ref('geprueft')
const kompNotiz = ref('')
const kompBusy = ref(false)
const kompMeldung = ref('')
/** Gerechneter Befund je Release-Version — Schlüssel ist die Version. */
const kompBefunde = ref<Record<string, any>>({})

const befundFuer = (s: any) => kompBefunde.value[String(s?.release_version || '')] || null

// #1761: Wie viele Komponenten sind zu dieser SBOM erfasst? Der Server liefert
// `liste_anzahl` mit der SBOM-Liste; der bereits geladene Store hat Vorrang,
// damit ein frischer Import sofort sichtbar ist, ohne die Liste neu zu holen.
const komponentenAnzahl = (s: any): number => {
  const geladen = (store.sbomKomponenten[String(s?.id)] || []).length
  if (geladen) return geladen
  return Number(s?.liste_anzahl || 0)
}
const komponentenVorhanden = (s: any): boolean => komponentenAnzahl(s) > 0

const ladeBefund = async (s: any) => {
  if (!s?.release_version) return
  const b = await store.fetchSbomVergleich(String(s.release_version))
  if (b) kompBefunde.value = { ...kompBefunde.value, [String(s.release_version)]: b }
}

const toggleKomponenten = async (s: any) => {
  kompMeldung.value = ''
  kompAuswahl.value = []
  if (offeneSbom.value === s.id) { offeneSbom.value = null; return }
  offeneSbom.value = s.id
  await Promise.all([store.fetchSbomKomponenten(s.id), ladeBefund(s)])
}

/** Schlüssel der neu aufgenommenen oder angehobenen Komponenten dieser SBOM. */
const pflichtKeys = (s: any): string[] => {
  const b = befundFuer(s)
  if (!b) return []
  return [...(b.vergleich?.neu || []), ...(b.vergleich?.angehoben || [])]
    .map((z: any) => String(z.komponent_key))
}
const istPflichtig = (s: any, k: any) =>
  pflichtKeys(s).includes(String(k?.komponent_key))

// #1774: Was gegen diese Komponente vorliegt — die Quelle steht mit dabei.
const befundTitel = (k: any): string => {
  const liste = k?.befunde || []
  if (!liste.length) return 'Kein Befund dieser Komponente zugeordnet'
  return liste.map((b: any) => `${b.cve_id || b.titel} · ${b.schwere} · `
    + `${b.offen ? 'offen' : b.status} · ${b.quelle_label}`).join('\n')
}

// #1773: Gruppenbewertung. Nach dem Übernehmen müssen Liste **und** Befund neu
// gelesen werden — der gerechnete Prüfpunkt hat sich geändert.
const klassenFuer = ref<any | null>(null)
const nachKlassenBewertung = async () => {
  const s = klassenFuer.value
  if (!s) return
  await Promise.all([store.fetchSbomKomponenten(s.id), ladeBefund(s)])
}

const auswahlPflichtig = (s: any) => {
  const keys = pflichtKeys(s)
  kompAuswahl.value = (store.sbomKomponenten[String(s.id)] || [])
    .filter((k: any) => keys.includes(String(k.komponent_key)))
    .map((k: any) => k.id)
}

const sbomDatei = async (s: any, ev: Event) => {
  const datei = (ev.target as HTMLInputElement)?.files?.[0]
  if (!datei) return
  kompBusy.value = true
  kompMeldung.value = ''
  try {
    const res = await store.importSbomKomponenten(s.id, { sbom: await datei.text() })
    kompMeldung.value = res
      ? `${res.gespeichert} Komponente(n) gelesen (${res.format || 'Liste'})`
        + (res.bewertungen_uebernommen
          ? `, ${res.bewertungen_uebernommen} Bewertung(en) übernommen` : '')
      : `⚠ ${store.error}`
    if (res) await Promise.all([ladeBefund(s), store.fetchPflichtDokuStatus()])
  } finally {
    kompBusy.value = false
    ;(ev.target as HTMLInputElement).value = ''
  }
}

const bewerteAuswahl = async (s: any) => {
  kompBusy.value = true
  kompMeldung.value = ''
  try {
    const ok = await store.bewerteSbomKomponenten(
      kompAuswahl.value, kompStatus.value, kompNotiz.value)
    if (!ok) { kompMeldung.value = `⚠ ${store.error}`; return }
    kompAuswahl.value = []
    kompNotiz.value = ''
    await Promise.all([store.fetchSbomKomponenten(s.id), ladeBefund(s)])
  } finally {
    kompBusy.value = false
  }
}

const reload = async () => {
  if (!store.selectedProjekt) return
  offeneSbom.value = null
  kompAuswahl.value = []
  kompBefunde.value = {}
  await store.fetchSboms()
}

onMounted(reload)
watch(() => store.selectedProjekt, reload)
</script>

<style scoped>
.sbom-panel { display: flex; flex-direction: column; gap: 16px; }

.info-banner { background: #e3f2fd; padding: 16px 20px; border-radius: 8px; border-left: 4px solid #1565c0; }
.info-banner h3 { margin: 0 0 8px; color: #1565c0; }
.info-banner p { margin: 0; color: #444; line-height: 1.5; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.zurueck { font-size: 13px; color: #1565c0; font-weight: 600; margin-left: auto; }

.section-full { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 16px 20px; }

.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; margin-bottom: 12px; }
.form-grid input, .form-grid select, .form-grid textarea {
  padding: 8px 10px; border: 1px solid #ccc; border-radius: 4px; font: inherit; min-width: 0;
}
.form-grid textarea { grid-column: 1 / -1; }

.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-primary:hover { background: #0d47a1; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-link { background: none; border: none; cursor: pointer; font-size: 16px; }
.btn-mini {
  font-size: 12px; padding: 3px 8px; margin-left: 4px; border-radius: 4px;
  border: 1px solid #1565c0; background: #fff; color: #1565c0; cursor: pointer;
}
.btn-mini:disabled { opacity: 0.5; cursor: default; }
.muted { color: #90a4ae; }

/* #2062: breite Tabellen scrollen innerhalb des Panels statt die Seite zu dehnen. */
.tabelle-scroll { width: 100%; overflow-x: auto; }
.sbom-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.sbom-table th, .sbom-table td { padding: 6px 10px; text-align: left; border-bottom: 1px solid #eee; }
.sbom-table th { background: #f5f5f5; font-weight: 600; white-space: nowrap; }
.sbom-dl { color: #1565c0; }

/* #1761 — Komponentenliste je SBOM (Art. 13 Abs. 5) + Upstream-Meldung (Abs. 6) */
.komp-warn { margin-left: 6px; font-size: 12px; color: #e65100; white-space: nowrap; }
.sbom-einlesen { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 8px 0 4px; }
.hint-klein { font-size: 12px; color: #607d8b; }
.einlesen-meldung { font-size: 12px; color: #2e7d32; }
.komp-ok { margin-left: 6px; font-size: 12px; color: #2e7d32; white-space: nowrap; }
.komp-row > td { background: #fafafa; padding: 10px 12px; }
.komp-import { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 13px; }
.komp-meldung { color: #2e7d32; font-size: 12px; }
.komp-befund { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 10px 0; font-size: 13px; }
.komp-bewertung { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
.komp-bewertung select { padding: 5px 8px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.komp-notiz { flex: 1 1 260px; padding: 5px 8px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.komp-pill { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px;
  background: #eceff1; color: #37474f; white-space: nowrap; }
.komp-pill.neu { background: #e3f2fd; color: #1565c0; }
.komp-pill.hoch { background: #fff8e1; color: #e65100; }
.komp-pill.weg { background: #ffebee; color: #c62828; }
.komp-pill.offen { background: #fff3e0; color: #e65100; }
.komp-pill.geprueft { background: #e8f5e9; color: #2e7d32; }
.komp-pill.nicht_relevant { background: #ede7f6; color: #4527a0; }
.komp-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 6px; }
.komp-table th, .komp-table td { border-bottom: 1px solid #e0e0e0; padding: 4px 6px; text-align: left; }
.komp-table tr.komp-neu > td { background: #f1f8ff; }
</style>
