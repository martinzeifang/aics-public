<template>
  <div class="prueffragen-panel">
    <div class="toolbar">
      <input v-model="search" class="search" placeholder="Prüffragen durchsuchen…" />
      <select v-model="filterStatus" class="filter">
        <option value="all">Alle Status</option>
        <option v-for="s in statusWerte" :key="s" :value="s">{{ statusLabel(s) }}</option>
      </select>
      <!-- #1575: Filter auf DSGVO-TOM-relevante Prüffragen (WiBA-Erfüllung belegt die TOM) -->
      <select v-model="filterTom" class="filter" title="Prüffragen, die DSGVO-TOM (Art. 32) belegen">
        <option value="all">Alle Prüffragen</option>
        <option value="relevant">🔐 nur TOM-relevante ({{ tomRelevantCount }})</option>
        <option v-for="t in tomMap.toms" :key="t.key" :value="t.key">🔐 {{ t.key }} · {{ t.titel }}</option>
      </select>
      <button class="btn-secondary" @click="massOpen = true" title="Mehrere Prüffragen über einen Sammel-Prompt bewerten">🧮 Massenbewertung</button>
      <button class="btn-secondary" @click="autoMassOpen = true" :disabled="!store.selectedProjekt"
              title="Mehrere Prüffragen nacheinander automatisch per KI bewerten (#1573)">🤖 Automatische Massenbewertung</button>
      <span class="info">{{ totalVisible }} Prüffragen</span>
    </div>

    <div v-if="store.themen.length === 0" class="empty">
      Keine Prüffragen geladen — bitte zuerst ein Projekt auswählen.
    </div>

    <!-- Themen (collapsible) → Tabelle je Thema -->
    <div v-for="t in visibleThemen" :key="t.theme_key" class="thema-block">
      <button class="thema-head" @click="toggle(t.theme_key)">
        <span class="caret">{{ open[t.theme_key] ? '▾' : '▸' }}</span>
        <span class="thema-titel">{{ t.titel }}</span>
        <span class="thema-progress" v-if="reifegradFor(t.theme_key)">
          {{ reifegradFor(t.theme_key)?.pct ?? 0 }}%
        </span>
        <span class="thema-count">{{ filterFragen(t.prueffragen).length }} / {{ t.prueffragen.length }} Fragen</span>
      </button>

      <div v-if="open[t.theme_key]" class="thema-body">
        <div v-if="t.bausteine" class="bausteine">
          <strong>BSI-Bausteine:</strong>
          <span v-for="b in bausteinChips(t.bausteine)" :key="b" class="baustein-tag">{{ b }}</span>
        </div>
        <p v-if="t.ziel" class="thema-ziel"><strong>Ziel:</strong> {{ t.ziel }}</p>

        <table class="frage-table">
          <thead>
            <tr>
              <th class="c-nr">Nr</th>
              <th>Prüffrage</th>
              <th class="c-status">Status</th>
              <th class="c-auf">Aufwand</th>
              <th class="c-ind"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in filterFragen(t.prueffragen)" :key="f.control_id"
                class="frage-row" @click="openDetail(f)">
              <td class="c-nr"><span class="frage-nr">{{ f.nr }}</span></td>
              <td class="c-frage">{{ f.frage }}
                <span v-for="k in (tomMap.controls[f.control_id] || []).slice(0, 3)" :key="k.key" class="tom-chip"
                      :title="`Belegt DSGVO-TOM ${k.key}: ${k.titel}`">🔐 {{ k.key }}</span>
              </td>
              <td class="c-status">
                <span class="status-pill" :style="pillStyle(drafts[f.control_id]?.status || f.status)">
                  {{ statusLabel(drafts[f.control_id]?.status || f.status || 'offen') }}
                </span>
              </td>
              <td class="c-auf">{{ f.aufwand || '—' }}</td>
              <td class="c-ind">
                <span v-if="(drafts[f.control_id]?.notiz || f.notiz)" title="Notiz vorhanden">📝</span>
                <span v-if="(drafts[f.control_id]?.evidence_doc_ids || []).length" title="Nachweis(e)">📎</span>
                <span class="open-caret">›</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Detail-Modal (Prüffrage bearbeiten) -->
    <div v-if="detail.open && activeFrage" class="modal-overlay" @mousedown.self="closeDetail">
      <div class="modal-content detail-modal">
        <div class="modal-header">
          <h3><span class="frage-nr">{{ activeFrage.nr }}</span> Prüffrage bearbeiten</h3>
          <button class="btn-close" @click="closeDetail">✕</button>
        </div>
        <div class="modal-body">
          <p class="detail-frage">{{ activeFrage.frage }}</p>
          <div v-if="(tomMap.controls[activeFrage.control_id] || []).length" class="tom-box-info">
            🔐 <strong>Relevant für DSGVO-TOM (Art. 32):</strong>
            <span v-for="k in tomMap.controls[activeFrage.control_id]" :key="k.key" class="tom-chip">{{ k.key }} · {{ k.titel }}</span>
            <span class="muted-small">— die Antwort fließt automatisch in den TOM-Status der Firma ein.</span>
          </div>
          <div v-if="activeFrage.hilfsmittel" class="help-box">
            <strong>BSI-Hilfsmittel:</strong> {{ activeFrage.hilfsmittel }}
          </div>

          <label class="fld-lbl">Status</label>
          <div class="status-row">
            <button
              v-for="s in statusWerte" :key="s" type="button" class="status-btn"
              :class="{ active: drafts[activeFrage.control_id]?.status === s }"
              :style="drafts[activeFrage.control_id]?.status === s ? activeStyle(s) : {}"
              @click="setStatus(activeFrage, s)"
            >{{ statusLabel(s) }}</button>
          </div>

          <!-- #1765: Herkunfts-/Prüfhinweis an der Notiz, in der die KI-Antwort steht. -->
          <KiHerkunftBadge
            v-if="store.selectedProjekt"
            modul="wiba"
            :projekt="store.selectedProjekt"
            art="wiba_control"
            :objekt-id="activeFrage.control_id"
          />

          <div class="fields-grid">
            <label class="full">Notiz / Nachweisbeschreibung
              <textarea v-model="drafts[activeFrage.control_id].notiz" rows="3"
                        placeholder="Bemerkung, Umsetzungshinweis, Verweis auf Dokument…"></textarea>
            </label>
            <label>Verantwortlich
              <input v-model="drafts[activeFrage.control_id].verantwortlich" placeholder="Name / Rolle" />
            </label>
            <label>Zieldatum
              <input v-model="drafts[activeFrage.control_id].zieldatum" type="date" />
            </label>
          </div>

          <!-- Nachweise -->
          <div class="evidence-row">
            <label class="ev-lbl">📎 Nachweis(e)</label>
            <select multiple class="ev-select" v-model="drafts[activeFrage.control_id].evidence_doc_ids">
              <option v-for="d in firmenEvidence" :key="d.id" :value="d.id">
                {{ d.filename }}<span v-if="d.doc_type"> · {{ d.doc_type }}</span><span v-if="d.version"> (v{{ d.version }})</span>
              </option>
            </select>
            <button v-if="tomVorschlaege.length" type="button" class="btn-link"
                    @click="showTom = showTom === activeFrage.control_id ? '' : activeFrage.control_id">
              💡 Aus DSGVO-TOM ({{ tomVorschlaege.length }})
            </button>
          </div>
          <p v-if="!firmenEvidence.length" class="ev-hint">
            Keine Firmen-Nachweise vorhanden — bei der Firma hochladen, dann hier wählbar.
          </p>

          <!-- TOM-Vorschläge -->
          <div v-if="showTom === activeFrage.control_id" class="tom-box">
            <div class="tom-head">
              <strong>DSGVO-TOM-Maßnahmen als Nachweis</strong>
              <button class="btn-tiny" @click="showTom = ''">✕</button>
            </div>
            <div v-for="(m, i) in tomVorschlaege" :key="i" class="tom-item">
              <span class="tom-status">{{ m.titel || m.ziel }}</span>
              <span class="tom-meta">{{ m.dsgvo_projekt }}<span v-if="m.wirksamkeit_ergebnis"> · {{ m.wirksamkeit_ergebnis }}</span></span>
              <button class="btn-tiny add" @click="addTomNote(activeFrage, m)" title="Als Notiz-Verweis übernehmen">＋</button>
            </div>
          </div>

          <!-- #1573: KI-Bewertung wie in allen Modulen (Prompt → Antwort | automatisch) -->
          <label class="fld-lbl">🤖 KI-Bewertung</label>
          <div class="issue-area">
            <button class="btn-secondary mini" @click="openPrompt(activeFrage)">🤖 KI-Bewertung (Prompt → Antwort)</button>
            <button class="btn-secondary mini" @click="openAuto(activeFrage, {})"
                    title="LLM direkt aufrufen und Antwort übernehmen">🤖 Automatische Bewertung</button>
          </div>

          <!-- Issues -->
          <label class="fld-lbl">Issue-Tracking</label>
          <div class="issue-area">
            <span v-for="iss in (issues[activeFrage.control_id] || [])" :key="iss.link_id || iss.id" class="issue-pill">
              <a v-if="iss.url" :href="safeUrl(iss.url)" target="_blank" rel="noopener" class="issue-link">#{{ iss.issue_number || iss.number || iss.id }}</a>
              <span v-else class="issue-link">#{{ iss.issue_number || iss.number || iss.id }}</span>
              <span class="issue-state" :class="(iss.state || iss.status || 'open')">{{ iss.state || iss.status || 'open' }}</span>
              <button class="btn-tiny" title="Verknüpfung entfernen" @click="unlink(activeFrage, iss.link_id || iss.id)">✕</button>
            </span>
            <button class="btn-secondary mini" @click="createIssue(activeFrage)" :disabled="busy[activeFrage.control_id] === 'issue'">
              {{ busy[activeFrage.control_id] === 'issue' ? '⏳…' : '🐙 Issue anlegen' }}
            </button>
            <button v-if="(issues[activeFrage.control_id] || []).length" class="btn-secondary mini"
                    @click="syncIssues(activeFrage)" :disabled="busy[activeFrage.control_id] === 'sync'">
              {{ busy[activeFrage.control_id] === 'sync' ? '⏳…' : '🔄 Sync' }}
            </button>
            <!-- #1521/#1524: Issue-Inhalt übernehmen (Antwort-neutral) + Neubewertung mit Feedback (immer sichtbar) -->
            <button class="btn-secondary mini"
                    @click="wibaImport.open = true" :disabled="busy[activeFrage.control_id] === 'import'"
                    title="Issue-/Review-Feedback in die Notiz übernehmen — Antwort bleibt">
              {{ busy[activeFrage.control_id] === 'import' ? '⏳…' : '📥 Issue-Inhalt importieren' }}
            </button>
            <button class="btn-secondary mini"
                    @click="openAuto(activeFrage, { use_issue_feedback: true })"
                    title="KI-Neubewertung unter Einbezug des Issue-Feedbacks">
              🔄 Neubewertung mit Issue-Feedback
            </button>
          </div>
          <p v-if="String(drafts[activeFrage.control_id]?.notiz || activeFrage.notiz || '').includes('Neubewertung erforderlich')"
             class="reassess-badge">⚠️ Neubewertung erforderlich —
            {{ String(drafts[activeFrage.control_id]?.notiz || activeFrage.notiz || '').includes('Pentest-Finding')
              ? 'ein Pentest-Finding widerspricht der Antwort (Details in der Notiz).'
              : 'ein verknüpftes Issue wurde geändert.' }}</p>

          <div v-if="msg[activeFrage.control_id]" :class="['frage-msg', msgKind[activeFrage.control_id]]">
            {{ msg[activeFrage.control_id] }}
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="promote(activeFrage)" :disabled="busy[activeFrage.control_id] === 'risk'">
            {{ busy[activeFrage.control_id] === 'risk' ? '⏳…' : '⚠️ Als Risiko' }}
          </button>
          <span class="footer-spacer"></span>
          <button class="btn-secondary" @click="closeDetail">Schließen</button>
          <button class="btn-primary" :disabled="busy[activeFrage.control_id] === 'save'" @click="save(activeFrage)">
            {{ busy[activeFrage.control_id] === 'save' ? '⏳ Speichern…' : '💾 Speichern' }}
          </button>
        </div>
      </div>
    </div>

    <!-- #1521/#1524: Issue-Inhalt importieren (Text einfügen oder aus verknüpften Issues) -->
    <div v-if="wibaImport.open && activeFrage" class="modal-overlay" @mousedown.self="wibaImport.open = false">
      <div class="modal-content prompt-modal">
        <div class="modal-header">
          <h3>📥 Issue-Inhalt importieren — {{ activeFrage.control_id }}</h3>
          <button class="btn-close" @click="wibaImport.open = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">Übernimmt Review-Feedback in die <strong>Notiz</strong> — die Antwort (offen/ja/nein/nicht_relevant) bleibt <strong>unverändert</strong>.</p>
          <button v-if="(issues[activeFrage.control_id] || []).length" class="btn-secondary"
                  :disabled="busy[activeFrage.control_id] === 'import'"
                  @click="importIssue(activeFrage)" style="margin-bottom:8px">
            🔗 Aus verknüpften Issues laden &amp; übernehmen
          </button>
          <textarea v-model="wibaImport.text" rows="9"
                    placeholder="Issue-Body, Kommentare, Review-Feedback…"></textarea>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="wibaImport.open = false">Abbrechen</button>
          <button class="btn-primary" :disabled="!wibaImport.text.trim() || busy[activeFrage.control_id] === 'import'"
                  @click="importIssue(activeFrage, wibaImport.text)">In Notiz einfügen</button>
        </div>
      </div>
    </div>

    <!-- #1573: gemeinsames KI-Wizard-Modal (Prompt → Antwort, inkl. ⚡ Direkt mit KI) wie in allen Modulen -->
    <WizardPromptModal v-if="promptModal.open" :title="`KI-Bewertung: ${promptModal.frage}`"
      :prompt="promptModal.prompt" :busy="promptModal.busy" force-json
      schema-hint='Antwort als JSON: { "status": "ja|nein|nicht_relevant", "notiz": "…", "empfehlung": "…" }'
      @apply="parsePromptApply" @close="closePrompt">
      <template #before>
        <!-- #1527: Transparenz — welche verknüpften Issues fließen in die Neubewertung ein? -->
        <div v-if="promptModal.useIssueFeedback" class="reassess-source">
          <template v-if="(issues[promptModal.controlId] || []).length">
            🔗 Es {{ (issues[promptModal.controlId] || []).length === 1 ? 'wird der Inhalt von 1 verknüpften Issue' : `werden die Inhalte von ${(issues[promptModal.controlId] || []).length} verknüpften Issues` }} in den Prompt einbezogen:
            <ul class="reassess-issue-list">
              <li v-for="i in (issues[promptModal.controlId] || [])" :key="i.link_id || i.id">
                <span class="issue-state" :class="i.state || i.status || 'open'">{{ i.state || i.status || 'open' }}</span>
                #{{ i.issue_number || i.number || i.id }} – {{ i.title || '(ohne Titel)' }}
              </li>
            </ul>
          </template>
          <template v-else>
            ⚠️ Keine verknüpften Issues — der Prompt enthält kein zusätzliches Issue-Feedback.
          </template>
        </div>
        <label class="check-row">
          <input type="checkbox" v-model="promptIncludeEvidence" @change="reloadPrompt" />
          Firmen-Nachweise einbeziehen
          <span v-if="promptModal.evidenceUsed?.length" class="evidence-note">
            📎 {{ promptModal.evidenceUsed.length }} Nachweis(e) berücksichtigt
          </span>
        </label>
        <FehlerHinweis :text="promptModal.error" @close="promptModal.error = ''" />
      </template>
      <template #after>
        <OutputDestinationHint destination="Setzt die Antwort (Ja/Nein/Nicht relevant) und die Notiz der Prüffrage."
                               impact="Überschreibt die aktuelle Antwort und Notiz." />
      </template>
    </WizardPromptModal>

    <!-- #1528/#1573: dieselbe Massenbewertung wie in allen Modulen -->
    <MassAssessmentModal v-if="massOpen && store.selectedProjekt" :projekt-name="store.selectedProjekt"
                         :adapter="wibaMassAdapter" @close="massOpen = false" @applied="onMassApplied" />
    <AutoMassBewertungModal v-if="autoMassOpen && store.selectedProjekt" :projekt-name="store.selectedProjekt"
                            :adapter="wibaMassAdapter" @close="autoMassOpen = false" @done="onMassApplied" />
    <!-- #1573: einheitlicher Auto-Bewertungs-Dialog -->
    <AutoBewertungDialog v-if="autoDlg.open && store.selectedProjekt" :title="autoDlg.title"
      :stream-url="wibaMassAdapter.streamUrl(autoDlg.id)" :body="autoDlg.body"
      :preview-fields="autoPreview" wert-label="Antwort"
      destination="Die KI beantwortet die Prüffrage direkt; Antwort und Notiz werden übernommen."
      impact="Überschreibt die aktuelle Antwort und Notiz (Verantwortlich, Zieldatum, Nachweise bleiben)."
      @close="autoDlg.open = false" @done="onMassApplied" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { safeUrl } from '../../utils/safeUrl'  // #1175: Schema-Allowlist für Issue-Links
import { useWibaStore, type WiBAPrueffrage } from '../../stores/wiba'
import MassAssessmentModal from '../../components/shared/MassAssessmentModal.vue'
import AutoMassBewertungModal from '../../components/shared/AutoMassBewertungModal.vue'
import AutoBewertungDialog from '../../components/shared/AutoBewertungDialog.vue'
import WizardPromptModal from '../../components/shared/WizardPromptModal.vue'
import OutputDestinationHint from '../../components/shared/OutputDestinationHint.vue'
import KiHerkunftBadge from '../../components/shared/KiHerkunftBadge.vue'
import { useKiHerkunftStore } from '../../stores/kiHerkunft'
import { wibaAdapter } from '../../utils/massAdapters'
import apiClient from '../../api/client'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'

const store = useWibaStore()
// #1765: Herkunfts-Karte nach KI-Antworten nachziehen (Einzel- und Massenlauf).
const kiHerkunft = useKiHerkunftStore()

const emit = defineEmits<{
  (e: 'changed'): void
}>()

// #1528: Massenbewertung mehrerer Prüffragen über einen Sammel-Prompt
const massOpen = ref(false)
const allControls = computed(() =>
  store.themen.flatMap((t: any) => (t.prueffragen || []).map((f: any) => ({
    control_id: f.control_id, frage: f.frage,
    status: f.status || 'offen', notiz: f.notiz || '',
  }))))
const autoMassOpen = ref(false)  // #1573
const wibaMassAdapter = computed(() => wibaAdapter(store.selectedProjekt || '', allControls.value))
// #1573: automatische Einzelbewertung (einheitlicher Dialog)
const autoDlg = ref<{ open: boolean; id: string; title: string; body: any }>({ open: false, id: '', title: '', body: {} })
function openAuto(f: any, body: any) {
  autoDlg.value = { open: true, id: f.control_id, title: `${f.nr || f.control_id}: ${String(f.frage || "").slice(0, 60)}`, body }
}
const autoPreview = computed(() => {
  const f = allControls.value.find(c => c.control_id === autoDlg.value.id)
  return [
    { label: 'Projekt', value: store.selectedProjekt },
    { label: 'Prüffrage', value: f?.frage },
    { label: 'Aktuelle Antwort', value: statusLabel(f?.status || 'offen') },
    { label: 'Nachweise', value: 'Bei der Firma hochgeladene Nachweise (Auszüge)' },
  ]
})
async function onMassApplied() {
  if (store.selectedProjekt) await store.fetchProjekt(store.selectedProjekt)
  // #1765: ohne das erschiene der Hinweis „KI-Entwurf, ungeprüft" erst nach
  // einem Neuladen der Seite.
  kiHerkunft.reload('wiba', store.selectedProjekt, 'wiba_control')
  emit('changed')
}

// ── Konstanten / Status ──────────────────────────────────────────────────
const statusWerte = computed<string[]>(() => store.constants?.status_werte || ['ja', 'nein', 'nicht_relevant'])
const statusMeta = computed<Record<string, any>>(() => store.constants?.status_meta || {})
const statusLabel = (s: string): string => statusMeta.value?.[s]?.label || s || 'Offen'
// Backend liefert die Farbe als `farbe` (deutsch); `color` als Fallback.
const statusColor = (s: string): string =>
  statusMeta.value?.[s]?.farbe || statusMeta.value?.[s]?.color || '#9e9e9e'
const activeStyle = (s: string) => ({ background: statusColor(s), color: '#fff', borderColor: statusColor(s) })
const pillStyle = (s?: string) => {
  const k = s || 'offen'
  return { background: statusColor(k), color: '#fff' }
}

const bausteinChips = (s?: string): string[] =>
  (s || '').split(';').map((x) => x.trim()).filter(Boolean)

// ── UI-State ─────────────────────────────────────────────────────────────
const search = ref('')
const filterStatus = ref('all')
const open = reactive<Record<string, boolean>>({})
const busy = reactive<Record<string, string | undefined>>({})
const msg = reactive<Record<string, string>>({})
const msgKind = reactive<Record<string, 'ok' | 'err'>>({})
const showTom = ref('')

// Draft je Prüffrage (lokale Bearbeitung vor Speichern)
const drafts = reactive<Record<string, {
  status: string
  notiz: string
  verantwortlich: string
  zieldatum: string
  evidence_doc_ids: (string | number)[]
}>>({})

const issues = reactive<Record<string, any[]>>({})
const firmenEvidence = ref<any[]>([])
const tomVorschlaege = ref<any[]>([])

const seedDrafts = () => {
  for (const t of store.themen) {
    if (open[t.theme_key] === undefined) open[t.theme_key] = false
    for (const f of t.prueffragen) {
      drafts[f.control_id] = {
        status: f.status || '',
        notiz: f.notiz || '',
        verantwortlich: f.verantwortlich || '',
        zieldatum: f.zieldatum || '',
        evidence_doc_ids: Array.isArray(f.evidence_doc_ids) ? [...f.evidence_doc_ids] : [],
      }
    }
  }
}

watch(() => store.themen, seedDrafts, { deep: false })

// ── Filter ───────────────────────────────────────────────────────────────
// #1575: DSGVO-TOM-Bezug je Prüffrage (Mapping aus dem Backend, Single Source of Truth)
const filterTom = ref('all')
const tomMap = ref<{ controls: Record<string, { key: string; titel: string; ziel: string }[]>;
                     toms: { key: string; titel: string; ziel: string }[] }>({ controls: {}, toms: [] })
const tomRelevantCount = computed(() =>
  store.themen.reduce((n: number, t: any) => n + (t.prueffragen || []).filter((f: any) => tomMap.value.controls[f.control_id]).length, 0))
async function loadTomMap() {
  try { tomMap.value = (await apiClient.get('/wiba/tom-mapping')).data } catch { /* optional */ }
}

const filterFragen = (fragen: WiBAPrueffrage[]): WiBAPrueffrage[] => {
  let list = fragen
  if (filterTom.value === 'relevant') list = list.filter(f => tomMap.value.controls[f.control_id])
  else if (filterTom.value !== 'all') {
    list = list.filter(f => (tomMap.value.controls[f.control_id] || []).some(k => k.key === filterTom.value))
  }
  if (filterStatus.value !== 'all') {
    list = list.filter(f => (drafts[f.control_id]?.status || f.status || 'offen') === filterStatus.value)
  }
  if (search.value) {
    const q = search.value.toLowerCase()
    list = list.filter(f =>
      (f.frage || '').toLowerCase().includes(q) ||
      String(f.nr || '').toLowerCase().includes(q) ||
      (f.hilfsmittel || '').toLowerCase().includes(q),
    )
  }
  return list
}

const visibleThemen = computed(() =>
  store.themen.filter(t => filterFragen(t.prueffragen).length > 0 || (!search.value && filterStatus.value === 'all' && filterTom.value === 'all')),
)

const totalVisible = computed(() =>
  store.themen.reduce((sum, t) => sum + filterFragen(t.prueffragen).length, 0),
)

const reifegradFor = (key: string) => store.reifegrad?.themen?.[key] || null

// ── Toggles ──────────────────────────────────────────────────────────────
const toggle = (key: string) => { open[key] = !open[key] }
const setStatus = (f: WiBAPrueffrage, s: string) => {
  if (drafts[f.control_id]) drafts[f.control_id].status = s
}

const flash = (cid: string, text: string, kind: 'ok' | 'err' = 'ok') => {
  msg[cid] = text; msgKind[cid] = kind
  setTimeout(() => { if (msg[cid] === text) msg[cid] = '' }, 4000)
}

// ── Detail-Modal ──────────────────────────────────────────────────────────
const detail = reactive<{ open: boolean; control_id: string }>({ open: false, control_id: '' })

const activeFrage = computed<WiBAPrueffrage | null>(() => {
  if (!detail.open || !detail.control_id) return null
  for (const t of store.themen) {
    const f = t.prueffragen.find((x: WiBAPrueffrage) => x.control_id === detail.control_id)
    if (f) return f
  }
  return null
})

const openDetail = async (f: WiBAPrueffrage) => {
  if (!drafts[f.control_id]) seedDrafts()
  detail.open = true
  detail.control_id = f.control_id
  showTom.value = ''
  await loadIssues(f.control_id)
}

const closeDetail = () => { detail.open = false; detail.control_id = '' }

// ── Speichern ────────────────────────────────────────────────────────────
const save = async (f: WiBAPrueffrage) => {
  const d = drafts[f.control_id]
  if (!d) return
  busy[f.control_id] = 'save'
  const res = await store.saveAntwort({
    control_id: f.control_id,
    status: d.status,
    notiz: d.notiz,
    verantwortlich: d.verantwortlich,
    zieldatum: d.zieldatum,
    evidence_doc_ids: d.evidence_doc_ids,
  })
  busy[f.control_id] = undefined
  if (res?.ok) {
    flash(f.control_id, '✓ Gespeichert')
    emit('changed')
  } else {
    flash(f.control_id, store.error || 'Fehler beim Speichern', 'err')
  }
}

// ── Risiko ───────────────────────────────────────────────────────────────
const promote = async (f: WiBAPrueffrage) => {
  busy[f.control_id] = 'risk'
  const res = await store.promoteRisk(f.control_id, {
    titel: f.frage,
    beschreibung: drafts[f.control_id]?.notiz || '',
  })
  busy[f.control_id] = undefined
  if (res?.ok) {
    flash(f.control_id, `✓ Als Risiko übernommen (${res.rb_projekt || ''})`)
  } else {
    flash(f.control_id, store.error || 'Fehler bei der Risiko-Übernahme', 'err')
  }
}

// ── Issues ───────────────────────────────────────────────────────────────
const loadIssues = async (cid: string) => {
  issues[cid] = await store.fetchControlIssues(cid)
}

const createIssue = async (f: WiBAPrueffrage) => {
  busy[f.control_id] = 'issue'
  const res = await store.createControlIssue(f.control_id, {
    title: `WiBA: ${f.frage}`,
    body: drafts[f.control_id]?.notiz || '',
  })
  busy[f.control_id] = undefined
  if (res) {
    await loadIssues(f.control_id)
    flash(f.control_id, '✓ Issue angelegt')
  } else {
    flash(f.control_id, store.error || 'Issue-Anlage fehlgeschlagen', 'err')
  }
}

const syncIssues = async (f: WiBAPrueffrage) => {
  busy[f.control_id] = 'sync'
  await store.syncControlIssues(f.control_id)
  await loadIssues(f.control_id)
  busy[f.control_id] = undefined
}

const unlink = async (f: WiBAPrueffrage, linkId: string | number) => {
  const ok = await store.unlinkControlIssue(f.control_id, linkId)
  if (ok) await loadIssues(f.control_id)
}

// ── TOM-Nachweis-Vorschlag ────────────────────────────────────────────────
const addTomNote = (f: WiBAPrueffrage, m: any) => {
  const d = drafts[f.control_id]
  if (!d) return
  const ref = `TOM: ${m.titel || m.ziel} (${m.dsgvo_projekt})`
  d.notiz = d.notiz ? `${d.notiz}\n${ref}` : ref
  showTom.value = ''
}

// ── Prompt-Modal ──────────────────────────────────────────────────────────
const promptIncludeEvidence = ref(true)
const promptModal = ref<any>({ open: false, controlId: '', frage: '', prompt: '', evidenceUsed: [], busy: false, error: '' })

const openPrompt = async (f: WiBAPrueffrage, useIssueFeedback = false) => {
  promptModal.value = { open: true, controlId: f.control_id, frage: f.frage, prompt: '', evidenceUsed: [], useIssueFeedback, busy: false, error: '' }
  await reloadPrompt()
}

const reloadPrompt = async () => {
  if (!promptModal.value.open) return
  const res = await store.buildPrompt(promptModal.value.controlId, promptIncludeEvidence.value,
                                      !!promptModal.value.useIssueFeedback)
  promptModal.value.prompt = res?.prompt || ''
  promptModal.value.evidenceUsed = res?.evidence_used || []
}

// #1521/#1524: Issue-Inhalt in die Notiz übernehmen — Antwort (Status) bleibt unverändert.
const wibaImport = ref<{ open: boolean; text: string }>({ open: false, text: '' })
const importIssue = async (f: WiBAPrueffrage, issueContext = '') => {
  const cid = f.control_id
  busy[cid] = 'import'
  try {
    const res = await store.importControlIssue(cid, issueContext)
    if (res?.notiz !== undefined && drafts[cid]) drafts[cid].notiz = res.notiz
    if (res) wibaImport.value.open = false
    msg[cid] = res ? 'Issue-Inhalt übernommen (Antwort unverändert).' : (store.error || 'Import fehlgeschlagen.')
    msgKind[cid] = res ? 'ok' : 'err'
    emit('changed')
  } finally { busy[cid] = '' }
}

const closePrompt = () => { promptModal.value = { open: false, controlId: '', frage: '', prompt: '', evidenceUsed: [], busy: false, error: '' } }

const parsePromptApply = async (raw: string) => {
  const cid = promptModal.value.controlId
  promptModal.value.busy = true; promptModal.value.error = ''
  const res = await store.parseResponse(cid, raw, true)
  promptModal.value.busy = false
  if (res?.ok) {
    const p = res.parsed || {}
    if (drafts[cid]) {
      if (p.status) drafts[cid].status = p.status
      if (p.notiz) drafts[cid].notiz = p.notiz
    }
    emit('changed')
    closePrompt()
  } else {
    promptModal.value.error = store.error || 'Antwort konnte nicht verarbeitet werden.'
  }
}

// ── Init ─────────────────────────────────────────────────────────────────
const loadEvidence = async () => {
  const fe = await store.fetchFirmenEvidence()
  firmenEvidence.value = fe?.dokumente || []
  const tom = await store.fetchTomEvidence()
  tomVorschlaege.value = tom?.massnahmen || []
}

onMounted(async () => {
  seedDrafts()
  loadTomMap()
  if (store.selectedProjekt) await loadEvidence()
})

watch(() => store.selectedProjekt, async (n) => {
  if (n) {
    seedDrafts()
    await loadEvidence()
  }
})
</script>

<style scoped>
.prueffragen-panel { display: flex; flex-direction: column; gap: 12px; }

.toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.search { flex: 1; min-width: 220px; padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; }
.filter { padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; }
.info { color: #888; font-size: 12px; margin-left: auto; }

.empty { padding: 40px; text-align: center; color: #888; background: white; border: 1px solid var(--color-border); border-radius: 8px; }

.thema-block { background: white; border: 1px solid var(--color-border); border-radius: 8px; overflow: hidden; }
.thema-head {
  width: 100%; display: flex; align-items: center; gap: 10px; padding: 12px 16px;
  background: #f5f7fa; border: none; cursor: pointer; font-size: 15px; font-weight: 600; text-align: left;
}
.thema-head:hover { background: #eef2f7; }
.caret { color: #1565c0; width: 14px; }
.thema-titel { flex: 1; color: #222; }
.thema-progress { background: #e3f2fd; color: #1565c0; padding: 2px 10px; border-radius: 10px; font-size: 12px; font-weight: 700; }
.thema-count { font-size: 12px; color: #888; font-weight: 400; }

.thema-body { padding: 12px 16px; display: flex; flex-direction: column; gap: 10px; }
.bausteine { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 13px; }
.baustein-tag { background: #e3f2fd; color: #1565c0; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; font-family: monospace; }
.thema-ziel { font-size: 13px; color: #555; margin: 0; }

/* Tabelle */
.frage-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.frage-table thead th {
  text-align: left; padding: 8px 10px; border-bottom: 2px solid #e0e0e0;
  font-size: 11px; text-transform: uppercase; color: #888; letter-spacing: .03em;
}
.frage-row { cursor: pointer; border-bottom: 1px solid #f0f0f0; }
.frage-row:hover { background: #f3f8ff; }
.frage-table td { padding: 8px 10px; vertical-align: middle; }
.c-nr { width: 48px; }
.c-status { width: 130px; }
.c-auf { width: 80px; color: #888; }
.c-ind { width: 70px; text-align: right; color: #888; white-space: nowrap; }
.c-frage { color: #222; }
.frage-nr { background: #1565c0; color: white; padding: 1px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; font-family: monospace; }
.status-pill { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; }
.open-caret { color: #bbb; font-size: 16px; margin-left: 4px; }

/* Status-Buttons (Detail) */
.fld-lbl { display: block; margin-top: 14px; margin-bottom: 6px; font-weight: 600; font-size: 13px; color: #444; }
.status-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.status-btn {
  padding: 6px 14px; border: 1px solid var(--color-border); background: white;
  border-radius: 16px; cursor: pointer; font-size: 13px; font-weight: 600; color: #555;
}
.status-btn:hover { border-color: #1565c0; }
.help-box { background: #fff8e1; border: 1px solid #ffe082; border-radius: 4px; padding: 8px 12px; font-size: 13px; color: #5d4037; margin-top: 10px; }

.detail-frage { font-size: 15px; font-weight: 600; color: #222; margin: 0; }

.fields-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
.fields-grid label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; font-weight: 600; color: #444; }
.fields-grid label.full { grid-column: 1 / -1; }
.fields-grid input, .fields-grid textarea { padding: 6px 8px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; font: inherit; resize: vertical; }

.evidence-row { display: flex; align-items: flex-start; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.ev-lbl { font-size: 12px; font-weight: 600; color: #444; padding-top: 4px; }
.ev-select { min-width: 280px; min-height: 60px; padding: 4px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 12px; }
.ev-hint { font-size: 12px; color: #999; margin: 4px 0 0; }

.tom-box { background: #f3e5f5; border: 1px solid #ce93d8; border-radius: 6px; padding: 10px 12px; margin-top: 10px; }
.tom-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; font-size: 13px; color: #4a148c; }
.tom-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; }
.tom-status { flex: 1; }
.tom-meta { color: #888; }

.issue-area { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.issue-pill { display: inline-flex; align-items: center; gap: 4px; background: white; border: 1px solid #ddd; border-radius: 12px; padding: 2px 6px; font-size: 11px; }
.issue-link { color: #1565c0; text-decoration: none; font-weight: 600; }
.issue-link:hover { text-decoration: underline; }
.issue-state { padding: 0 6px; border-radius: 8px; font-size: 10px; font-weight: 600; text-transform: uppercase; }
.issue-state.open { background: #e3f2fd; color: #1565c0; }
.issue-state.closed { background: #e8f5e9; color: #2e7d32; }

.frage-msg { font-size: 12px; margin-top: 10px; }
.frage-msg.ok { color: #2e7d32; }
.frage-msg.err { color: #c62828; }

.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-primary:hover:not(:disabled) { background: #0d47a1; }
.btn-secondary { background: #e0e0e0; color: #333; border: none; padding: 8px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-secondary:hover:not(:disabled) { background: #d5d5d5; }
.btn-secondary.mini { padding: 6px 12px; font-size: 12px; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-link { background: none; border: none; cursor: pointer; color: #1565c0; font-size: 12px; padding: 0; align-self: center; }
.btn-tiny { background: none; border: 1px solid #ddd; width: 22px; height: 22px; border-radius: 3px; cursor: pointer; color: #888; font-size: 12px; }
.btn-tiny:hover { background: #ffebee; color: #c62828; }
.btn-tiny.add:hover { background: #e8f5e9; color: #2e7d32; }

/* Modale */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: white; border-radius: 8px; max-width: 760px; width: 95%; max-height: 90vh; display: flex; flex-direction: column; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid var(--color-border); gap: 10px; }
.modal-header h3 { margin: 0; color: #1565c0; font-size: 16px; display: flex; align-items: center; gap: 8px; }
.btn-close { background: none; border: none; font-size: 22px; color: #999; cursor: pointer; }
.modal-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.modal-footer { display: flex; align-items: center; gap: 8px; padding: 12px 20px; border-top: 1px solid var(--color-border); }
.footer-spacer { flex: 1; }
.prompt-text { background: #f5f5f5; padding: 12px; border-radius: 4px; font-size: 12px; line-height: 1.5; white-space: pre-wrap; max-height: 40vh; overflow-y: auto; font-family: monospace; border: 1px solid #ddd; }
.prompt-modal .modal-body label, .check-row { display: block; margin-top: 12px; font-weight: 600; font-size: 13px; }
.prompt-modal textarea { width: 100%; padding: 8px; border: 1px solid var(--color-border); border-radius: 4px; font-family: monospace; font-size: 12px; resize: vertical; }
.check-row { display: flex; align-items: center; gap: 8px; font-weight: 400 !important; cursor: pointer; }
.evidence-note { font-size: 12px; color: #2e7d32; margin-left: 12px; }
.hint { color: #666; font-size: 13px; }
.preview { background: #e8f5e9; padding: 10px 14px; border-radius: 4px; margin-top: 12px; font-size: 13px; border: 1px solid #81c784; }
.preview pre { white-space: pre-wrap; font-size: 12px; max-height: 200px; overflow-y: auto; }

@media (max-width: 768px) {
  .fields-grid { grid-template-columns: 1fr; }
  .c-auf, .c-ind { display: none; }
}
.reassess-badge {
  margin: 8px 0; padding: 6px 10px; border-radius: 8px;
  background: #fff3e0; color: #b26a00; font-size: 0.85em; font-weight: 600;
}
.reassess-source {
  margin: 8px 0; padding: 8px 12px; border-radius: 6px;
  background: #f5faff; border: 1px solid #cfe3f7; font-size: 13px; color: #37474f;
}
.reassess-issue-list { margin: 6px 0 0; padding-left: 4px; list-style: none; }
.reassess-issue-list li { padding: 2px 0; font-size: 12px; }
.tom-chip { display: inline-block; margin-left: 6px; padding: 0 6px; border-radius: 8px; background: #e8f5e9;
  color: #2e7d32; font-size: 10px; font-weight: 600; white-space: nowrap; }
.tom-box-info { background: #f1f8e9; border: 1px solid #c5e1a5; border-radius: 6px; padding: 8px 10px;
  font-size: 12px; margin-bottom: 10px; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.muted-small { color: #78909c; font-size: 11px; }
</style>
