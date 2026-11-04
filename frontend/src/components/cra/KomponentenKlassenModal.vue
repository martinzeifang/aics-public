<!--
  KomponentenKlassenModal (#1773/#1774) — Fremdkomponenten in Klassen bewerten.

  Eine echte SBOM führt 184 Komponenten; beim Erst-Release gilt jede als neu
  integriert. Der gerechnete Prüfpunkt nach Art. 13 Abs. 5 verlangte damit 184
  begründete Einzelaussagen — der Punkt, an dem jeder Anwender alles markiert
  und einen Satz für alles schreibt.

  Hier wird nach **Klasse × Ökosystem** gruppiert, weil der Sorgfaltsmaßstab
  dort tatsächlich verschieden ist (Basis-Image, Betriebssystem-Paket,
  Anwendungsabhängigkeit). Je Gruppe eine Begründung — als KI-Entwurf oder von
  Hand —, Status und Übernahme bleiben beim Menschen.

  Die Gruppe „Einzelprüfung" (#1774) steht oben und verlangt eine
  ausdrückliche Bestätigung: Gegen diese Komponenten liegt ein offener Befund
  vor, sie sind kein gleichartiger Fall.
-->
<template>
  <Teleport to="body">
    <div class="modal-overlay" @mousedown.self="$emit('close')">
      <div class="modal-content klassen-modal">
        <div class="modal-header">
          <h3>🧩 Fremdkomponenten nach Klassen bewerten</h3>
          <button class="btn-close" @click="$emit('close')">✕</button>
        </div>

        <div class="modal-body">
          <p class="kl-intro">
            Art. 13 Abs. 5 — Sorgfaltspflicht bei Komponenten Dritter.
            Gruppiert wird nach Herkunft und Ökosystem: Was gleich überwacht
            wird, trägt dieselbe Begründung. Was einen eigenen Befund hat, wird
            einzeln angesehen.
          </p>

          <p v-if="ladend" class="kl-wait">⏳ Gruppen werden gebildet …</p>
          <p v-else-if="!gruppen.length" class="kl-wait">
            Keine Komponenten erfasst — zuerst die SBOM einlesen.
          </p>

          <div v-else class="kl-kopf">
            <span class="komp-pill">{{ gesamt.komponenten }} Komponenten</span>
            <span class="komp-pill">{{ gruppen.length }} Gruppe(n)</span>
            <span class="komp-pill" :class="{ offen: gesamt.offen }">
              {{ gesamt.offen }} ohne Bewertung</span>
            <span v-if="version" class="muted">Release {{ version }}</span>
          </div>

          <div v-for="g in gruppen" :key="g.key"
               class="kl-gruppe" :class="{ einzel: !g.sammel }">
            <div class="kl-g-kopf" @click="offen = offen === g.key ? '' : g.key">
              <span class="kl-g-titel">
                {{ !g.sammel ? '⚠️' : '📦' }} {{ g.label }}
              </span>
              <span class="komp-pill">{{ g.anzahl }} Komponenten</span>
              <span class="komp-pill" :class="{ offen: g.offen }">
                {{ g.offen }} offen</span>
              <span v-if="g.pflichtig" class="komp-pill neu">
                {{ g.pflichtig }} in diesem Release neu/angehoben</span>
              <span v-if="g.ohne_lizenz" class="komp-pill hoch">
                {{ g.ohne_lizenz }} ohne Lizenzangabe</span>
              <span v-if="g.mit_befund" class="komp-pill weg">
                {{ g.mit_befund }} mit Befund</span>
              <span class="kl-g-pfeil">{{ offen === g.key ? '▾' : '▸' }}</span>
            </div>

            <div v-if="offen === g.key" class="kl-g-body">
              <p class="kl-g-text">{{ g.beschreibung }}</p>
              <p class="kl-g-soll"><strong>Zu belegen:</strong> {{ g.sorgfalt }}</p>
              <p v-if="g.beispiele?.length" class="muted kl-g-bsp">
                z.&nbsp;B. {{ g.beispiele.join(', ') }}<span v-if="g.anzahl > g.beispiele.length"> …</span>
              </p>
              <p v-if="g.lizenzen?.length" class="muted kl-g-bsp">
                Lizenzen: {{ g.lizenzen.join(', ') }}
                <span v-if="g.lizenzen_gesamt > g.lizenzen.length">
                  (von {{ g.lizenzen_gesamt }})</span>
              </p>

              <p v-if="!g.sammel" class="kl-g-warn">
                Gegen diese Komponenten steht ein offener Befund. Eine
                gemeinsame Begründung muss sagen, wie damit umgegangen wird —
                sonst bitte je Komponente in der Liste bewerten.
              </p>

              <div class="kl-aktionen">
                <button class="btn-mini" :disabled="busy" @click="holePrompt(g)">
                  ⚙ Prompt erzeugen
                </button>
                <button class="btn-mini" :disabled="busy" @click="mitKi(g)">
                  ⚡ Entwurf mit KI
                </button>
                <span v-if="g.key === promptFuer && prompt" class="muted">
                  Prompt bereit — kopieren oder direkt ausführen
                </span>
              </div>

              <details v-if="g.key === promptFuer && prompt" class="kl-prompt">
                <summary>Prompt ansehen ({{ prompt.length }} Zeichen)</summary>
                <!-- #1867: Kopieren **und** Einfügen. Die Antwort aus einem
                     KI-Werkzeug ist hier Prosa und landet im Begründungsfeld
                     unten — der Einfüge-Knopf steht deshalb daran. -->
                <PromptAustausch v-model="notizen[g.key]" :prompt="prompt"
                                 prompt-titel="Prompt" :prompt-zeilen="8"
                                 antwort-titel="Begründung aus dem KI-Werkzeug"
                                 :antwort-zeilen="5" :nummeriert="false"
                                 platzhalter="Antwort des KI-Werkzeugs hier einfügen …" />
              </details>

              <!-- #1834/#1836/E6: eigene Hinweise auch hier. Die Engine
                   setzt sie serverseitig ein (shared/ki_engine). -->
              <PromptZusatzFeld v-model="zusatz" modul="cra" bereich="bewertung" />
              <KiStreamView v-if="g.key === kiFuer && kiPrompt"
                            :key="'ki-' + g.key"
                            url="/api/ai/run-stream"
                            :body="{ prompt: kiPrompt, system: SYSTEM, prompt_zusatz: zusatz }"
                            :autostart="false" confirm-egress egress-modul="cra"
                            egress-context="CRA — Begründung je Komponentenklasse"
                            @done="kiFertig" />

              <div class="kl-form">
                <label>Begründung für diese Gruppe</label>
                <textarea v-model="notizen[g.key]" rows="5"
                          placeholder="Woher die Komponenten stammen, wie sie auf Schwachstellen überwacht werden und wie ein Update in das Produkt gelangt."></textarea>
                <p v-if="entwurfVon[g.key]" class="kl-entwurf">
                  🤖 KI-Entwurf ({{ entwurfVon[g.key] }}) — mit der Übernahme
                  bestätigen Sie ihn fachlich; die Herkunft wird festgehalten.
                </p>
                <div class="kl-form-zeile">
                  <select v-model="status[g.key]">
                    <option value="geprueft">geprüft</option>
                    <option value="nicht_relevant">nicht relevant</option>
                  </select>
                  <label class="kl-check">
                    <input type="checkbox" v-model="nurOffene" />
                    nur unbewertete Komponenten
                  </label>
                  <!-- Trifft die Übernahme keine Zeile, ist der Knopf aus: Ein
                       Klick brächte sonst nur die Meldung, dass nichts offen
                       ist — eine Frage, die die Zahl daneben schon beantwortet. -->
                  <button class="btn-primary"
                          :disabled="busy || !(notizen[g.key] || '').trim() || !zahl(g)"
                          @click="uebernehmen(g)">
                    Für {{ zahl(g) }} Komponente(n) übernehmen
                  </button>
                </div>
                <p v-if="meldung[g.key]" class="kl-meldung">{{ meldung[g.key] }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import PromptAustausch from '../shared/PromptAustausch.vue'
import PromptZusatzFeld from '../shared/PromptZusatzFeld.vue'
import { useCraStore } from '../../stores/cra'
import KiStreamView from '../shared/KiStreamView.vue'

const props = defineProps<{ sbomId: number; version?: string; artefakt?: string }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'geaendert'): void }>()

// Der Standard-System-Prompt verlangt JSON, wenn der Prompt es nahelegt. Hier
// soll **Prosa** entstehen: Der Text wird so, wie er kommt, die Begründung an
// der Komponente. Ein JSON-Gerüst darum müsste jemand wieder abtragen.
const SYSTEM = 'Du bist ein erfahrener Compliance-Experte für die EU-Verordnung '
  + '2024/2847 (Cyber Resilience Act). Du antwortest mit reinem Fließtext auf '
  + 'Deutsch, ohne Überschrift, ohne Aufzählung, ohne JSON, und du behauptest '
  + 'nichts, was in den übergebenen Angaben nicht steht.'

const store = useCraStore()
// #1834: eigene Hinweise des Bearbeiters für diesen Lauf.
const zusatz = ref('')
const gruppen = ref<any[]>([])
const version = ref(props.version || '')
const ladend = ref(true)
const busy = ref(false)
const offen = ref('')

const notizen = ref<Record<string, string>>({})
const status = ref<Record<string, string>>({})
const meldung = ref<Record<string, string>>({})
// Welcher Anbieter den Entwurf geschrieben hat — die Angabe landet im
// Herkunfts-Register (#1765) und darf deshalb nicht verloren gehen.
const entwurfVon = ref<Record<string, string>>({})
const nurOffene = ref(true)

const prompt = ref('')
const promptFuer = ref('')
const kiPrompt = ref('')
const kiFuer = ref('')

/** Wie viele Komponenten eine Übernahme jetzt träfe. */
const zahl = (g: any): number => (nurOffene.value ? (g?.offen || 0) : (g?.anzahl || 0))

const gesamt = computed(() => ({
  komponenten: gruppen.value.reduce((s, g) => s + (g.anzahl || 0), 0),
  offen: gruppen.value.reduce((s, g) => s + (g.offen || 0), 0),
}))

const laden = async () => {
  ladend.value = true
  const data = await store.fetchKomponentenKlassen(props.sbomId, props.version || '')
  gruppen.value = data?.gruppen || []
  version.value = data?.version || props.version || ''
  for (const g of gruppen.value) {
    if (!status.value[g.key]) status.value[g.key] = 'geprueft'
  }
  // Die erste Gruppe aufklappen — bei „Einzelprüfung" ist das die, die Arbeit
  // verlangt, und genau die soll man zuerst sehen.
  if (!offen.value && gruppen.value.length) offen.value = gruppen.value[0].key
  ladend.value = false
}
onMounted(laden)

const holePrompt = async (g: any) => {
  busy.value = true
  meldung.value = { ...meldung.value, [g.key]: '' }
  try {
    const data = await store.klassenPrompt(props.sbomId, g.key, version.value)
    if (!data) { meldung.value = { ...meldung.value, [g.key]: `⚠ ${store.error}` }; return }
    prompt.value = data.prompt || ''
    promptFuer.value = g.key
  } finally { busy.value = false }
}

const mitKi = async (g: any) => {
  await holePrompt(g)
  if (!prompt.value) return
  kiPrompt.value = prompt.value
  kiFuer.value = g.key
}

const kiFertig = (payload: any) => {
  if (!payload?.ok || !kiFuer.value) return
  const text = String(payload.text || payload.antwort || '').trim()
  if (!text) return
  notizen.value = { ...notizen.value, [kiFuer.value]: text }
  entwurfVon.value = { ...entwurfVon.value, [kiFuer.value]: payload.provider || 'KI' }
}


const uebernehmen = async (g: any, confirmEinzel = false) => {
  busy.value = true
  meldung.value = { ...meldung.value, [g.key]: '' }
  try {
    const res = await store.uebernehmeKlasse(props.sbomId, {
      gruppe: g.key,
      version: version.value,
      status: status.value[g.key] || 'geprueft',
      notiz: notizen.value[g.key] || '',
      nur_offene: nurOffene.value,
      ki_entwurf: !!entwurfVon.value[g.key],
      provider: entwurfVon.value[g.key] || '',
      confirm_einzel: confirmEinzel,
    })
    if (res?.confirm) {
      if (window.confirm(
        `${res.hinweis}\n\nFür ${res.anzahl} Komponente(n) trotzdem gemeinsam übernehmen?`)) {
        busy.value = false
        return uebernehmen(g, true)
      }
      return
    }
    if (!res?.ok) { meldung.value = { ...meldung.value, [g.key]: `⚠ ${store.error}` }; return }
    meldung.value = {
      ...meldung.value,
      [g.key]: `✓ ${res.geaendert} Komponente(n) bewertet`
        + (res.ki_vermerkt ? ` · Herkunft für ${res.ki_vermerkt} vermerkt` : ''),
    }
    emit('geaendert')
    await laden()
  } finally { busy.value = false }
}
</script>

<style scoped>
/* #1535: Overlay und Content brauchen eigene Regeln — scoped CSS, kein
   globales Modal-Stylesheet. Ohne sie landet der Teleport-Inhalt unsichtbar
   am Seitenende, und der Knopf sieht aus wie ohne Wirkung. */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 1100; padding: 1rem;
}
.modal-content {
  background: #fff; border-radius: 10px; box-shadow: 0 10px 40px rgba(0,0,0,0.25);
  overflow: hidden;
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.9rem 1.2rem; border-bottom: 1px solid #e0e0e0;
}
.modal-header h3 { margin: 0; font-size: 1.05rem; color: #1565c0; }
.btn-close { background: none; border: none; font-size: 1.1rem; cursor: pointer; color: #757575; }
.modal-body { padding: 1rem 1.2rem 1.2rem; overflow-y: auto; }
.klassen-modal { width: min(940px, 96vw); max-height: 90vh; display: flex; flex-direction: column; }

.kl-intro { margin: 0 0 10px; font-size: 13px; color: #555; }
.kl-wait { font-size: 13px; color: #757575; }
.kl-kopf { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.muted { color: #757575; font-size: 12px; }

.kl-gruppe { border: 1px solid #e0e0e0; border-radius: 6px; margin-bottom: 8px; }
.kl-gruppe.einzel { border-color: #ffab91; background: #fff8f6; }
.kl-g-kopf { display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 8px 10px; cursor: pointer; }
.kl-g-titel { font-weight: 600; font-size: 13px; flex: 1 1 240px; }
.kl-g-pfeil { color: #757575; }
.kl-g-body { padding: 0 10px 10px; border-top: 1px solid #eee; }
.kl-g-text { font-size: 12px; color: #555; margin: 8px 0 4px; }
.kl-g-soll { font-size: 12px; color: #333; margin: 4px 0; }
.kl-g-bsp { margin: 2px 0; }
.kl-g-warn { font-size: 12px; color: #c62828; background: #ffebee; border-radius: 4px;
  padding: 6px 8px; margin: 8px 0; }

.kl-aktionen { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
.kl-prompt { margin: 6px 0; font-size: 12px; }
.kl-prompt pre { white-space: pre-wrap; background: #fafafa; border: 1px solid #eee;
  border-radius: 4px; padding: 8px; max-height: 240px; overflow: auto; font-size: 11px; }

.kl-form { margin-top: 8px; }
.kl-form label { display: block; font-size: 12px; font-weight: 600; margin-bottom: 4px; }
.kl-form textarea { width: 100%; padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px;
  font: inherit; font-size: 13px; resize: vertical; }
.kl-form-zeile { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 8px; }
.kl-form-zeile select { padding: 5px 8px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.kl-check { display: flex; align-items: center; gap: 5px; font-weight: 400; font-size: 12px; margin: 0; }
.kl-entwurf { font-size: 12px; color: #1565c0; margin: 6px 0 0; }
.kl-meldung { font-size: 12px; color: #2e7d32; margin: 6px 0 0; }

.komp-pill { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px;
  background: #eceff1; color: #455a64; white-space: nowrap; }
.komp-pill.neu { background: #e3f2fd; color: #1565c0; }
.komp-pill.hoch { background: #fff8e1; color: #e65100; }
.komp-pill.weg { background: #ffebee; color: #c62828; }
.komp-pill.offen { background: #fff3e0; color: #e65100; }
.btn-mini { padding: 3px 8px; font-size: 12px; border: 1px solid #ccc; background: #fff;
  border-radius: 4px; cursor: pointer; }
.btn-mini:disabled { opacity: 0.5; cursor: default; }
.btn-primary { padding: 5px 12px; font-size: 13px; border: none; border-radius: 4px;
  background: #1565c0; color: #fff; cursor: pointer; }
.btn-primary:disabled { opacity: 0.5; cursor: default; }
</style>
