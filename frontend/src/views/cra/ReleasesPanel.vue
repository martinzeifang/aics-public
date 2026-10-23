<template>
  <!--
    #1747: Ein Tab für das CRA-Tagesgeschäft — drei Ebenen in EINER Ansicht.

    Phase 1 (ist das Produkt überhaupt CRA-ready?) steht als eine Zeile oben:
    Hier arbeitet niemand täglich, aber ohne sie ist jeder Release-Nachweis
    bodenlos. Darunter die Vorgänge je Release, darunter der geöffnete Vorgang.
    Kein zweiter Tab, kein Dialog — der Anwender soll den Zusammenhang sehen.
  -->
  <div class="releases-panel">
    <div class="panel-header">
      <h3>🚦 Releases</h3>
      <p class="sub">Bei jedem Release nachweisen, dass das Produkt konform geblieben ist
        (Phase 2). Vieles ist jedes Mal gleich, anderes muss jedes Mal geprüft werden.</p>
    </div>

    <!-- ── Ebene 1: Phase 1, eine Zeile ─────────────────────────────────── -->
    <div class="phase1" :class="phase1Ampel">
      <span class="dot" />
      <strong class="p1-label">CRA-ready</strong>
      <span class="p1-text">{{ phase1Text }}</span>
      <span v-if="craReady?.ueberholt" class="p1-warn"
            title="Die Feststellung steht, der heutige Rechenstand trägt sie nicht mehr.
Sie wird nicht gelöscht, sondern widersprochen.">⚠️ überholt — heutiger Stand trägt die Feststellung nicht</span>
      <span class="p1-spacer" />
      <template v-if="canApprove">
        <button v-if="craReady?.status !== 'bereit'" class="btn-secondary btn-mini"
                :disabled="busy" @click="feststellen">CRA-ready feststellen</button>
        <button v-else class="btn-secondary btn-mini" :disabled="busy"
                @click="entzugOffen = !entzugOffen">Feststellung entziehen</button>
      </template>
      <button class="btn-link" @click="$emit('goto', 'konformitaet')">→ Phase 1 pflegen</button>
    </div>
    <div v-if="entzugOffen && canApprove" class="form-card grund-card">
      <label>Begründung für den Entzug (Pflicht)</label>
      <textarea v-model="entzugGrund" rows="2"
                placeholder="Warum trägt die Feststellung nicht mehr?"></textarea>
      <div class="actions">
        <button class="btn-secondary" @click="entzugOffen = false">Abbrechen</button>
        <button class="btn-primary" :disabled="busy" @click="entziehen">Entzug speichern</button>
      </div>
    </div>
    <FehlerHinweis :text="p1Msg" :art="p1Err ? 'fehler' : 'erfolg'" @close="p1Msg = ''" />

    <!-- ── Ebene 2: Vorgänge je Release ─────────────────────────────────── -->
    <div class="form-card">
      <div class="card-head">
        <h4>Release-Vorgänge</h4>
        <div class="ver-input">
          <input v-model="version" list="rel-versions" placeholder="z. B. v1.2.0"
                 @keyup.enter="oeffnen(version)" />
          <datalist id="rel-versions">
            <option v-for="v in versions" :key="v" :value="v" />
          </datalist>
          <button class="btn-secondary" :disabled="busy || !version.trim()"
                  @click="oeffnen(version)">Vorgang öffnen</button>
        </div>
      </div>
      <p v-if="versions.length" class="hint-sub">{{ versions.length }} Version(en) aus
        {{ repo }} ({{ provider }})<span v-if="store.aktuelleVersion"> · aktuell
          {{ store.aktuelleVersion }}</span></p>
      <p v-else class="hint-sub muted">Keine Versionshistorie aus dem Repo abrufbar —
        Version manuell eingeben.</p>

      <ul v-if="store.releases.length" class="rel-list">
        <li v-for="r in store.releases" :key="r.release_version"
            :class="{ active: detail && detail.vorgang.release_version === r.release_version }"
            @click="oeffnen(r.release_version)">
          <strong class="rl-ver">{{ r.release_version }}</strong>
          <span class="status-pill" :class="r.freigabe_status">
            {{ statusLabel(r.freigabe_status) }}</span>
          <span v-if="r.wesentliche_aenderung" class="badge">
            wesentliche Änderung: {{ r.wesentliche_aenderung }}</span>
          <span class="rl-meta">
            <template v-if="r.erstellt_von">eingereicht von {{ r.erstellt_von }}</template>
            <template v-if="r.geprueft_von"> · geprüft von {{ r.geprueft_von }}</template>
            <template v-if="r.freigegeben_am"> · freigegeben {{ tag(r.freigegeben_am) }}</template>
            <template v-else-if="r.eingereicht_am"> · {{ tag(r.eingereicht_am) }}</template>
          </span>
          <button class="btn-link">öffnen →</button>
        </li>
      </ul>
      <p v-else class="hint-sub muted">Noch kein Release erfasst — oben eine Version wählen
        und den Vorgang öffnen.</p>
    </div>

    <p v-if="busy" class="muted">Lädt…</p>
    <FehlerHinweis :text="err" @close="err = ''" />

    <!-- ── Ebene 3: der geöffnete Vorgang ───────────────────────────────── -->
    <!-- Für eine Version ohne Vorgang wird NICHTS angelegt, nur angeboten.
         Ein GET, der schreibt, erzeugt aus einem Tippfehler im Link einen
         leeren Entwurf. -->
    <div v-if="detail && !detail.vorgang" class="form-card">
      <h4>Version {{ offeneVersion }} — noch kein Vorgang</h4>
      <p class="hint-sub">
        Für diese Version ist noch kein Release-Vorgang angelegt. Die Ampel zeigt
        schon, wie der Stand heute wäre: <strong>{{ ampelLabel(detail.gate.ampel) }}</strong>.
      </p>
      <button v-if="canWrite" class="btn-primary" :disabled="busy" @click="anlegen">
        ➕ Vorgang für {{ offeneVersion }} anlegen
      </button>
      <p v-else class="hint-sub">Anlegen braucht das Recht <code>cra:write</code>.</p>
    </div>

    <template v-if="detail && detail.vorgang">
      <div class="form-card ampel-card" :class="detail.gate.ampel">
        <div class="ampel-top">
          <span class="dot" />
          <strong>{{ detail.vorgang.release_version }} — {{ ampelLabel(detail.gate.ampel) }}</strong>
          <span class="status-pill" :class="detail.vorgang.freigabe_status">
            {{ statusLabel(detail.vorgang.freigabe_status) }}</span>
          <span class="pct">Reifegrad {{ detail.gate.reifegrad_pct }} %</span>
        </div>
        <div class="counts">
          <span class="ok">erfüllt {{ detail.gate.erfuellt }}</span>
          <span class="warn">begründet akzeptiert {{ detail.gate.begruendet_akzeptiert }}</span>
          <span :class="detail.gate.offen ? 'bad' : 'ok'">offen {{ detail.gate.offen }}</span>
          <span class="muted">/ {{ detail.gate.gesamt_anforderungen }} Anforderungen</span>
        </div>
        <div v-if="detail.vorgang.zurueckweisung_grund" class="rejected">
          ↩️ Zurückgewiesen<span v-if="detail.vorgang.geprueft_von"> von
            {{ detail.vorgang.geprueft_von }}</span>: {{ detail.vorgang.zurueckweisung_grund }}
        </div>
        <p v-if="detail.vorgang.gesperrt" class="hint-sub">
          🔒 Der Vorgang ist im Zustand „{{ statusLabel(detail.vorgang.freigabe_status) }}"
          gesperrt — Eingaben sind nicht mehr möglich.</p>
      </div>

      <!-- Checkliste, nach den drei Arten getrennt (#1744) -->
      <div v-for="g in gruppen" :key="g.art" class="form-card">
        <h4>{{ g.titel }}</h4>
        <p class="hint-sub">{{ g.erklaerung }}</p>
        <ul class="check-list">
          <li v-for="it in g.items" :key="it.id" :class="{ computed: it.art === 'gerechnet' }">
            <div class="ci-head">
              <span class="badge art" :title="g.titel">{{ g.badge }}</span>
              <span class="ci-label">{{ it.label }}</span>
              <span v-if="!it.pflicht" class="badge soft">freiwillig</span>
              <span class="ci-ref">{{ it.rechtsbezug }}</span>
              <button v-if="it.link" class="btn-link" @click="$emit('goto', it.link)">
                → hier pflegen</button>
            </div>
            <p v-if="it.erklaerung" class="ci-text">{{ it.erklaerung }}</p>

            <!-- gerechnet: Ergebnis, kein Eingabefeld -->
            <div v-if="it.art === 'gerechnet'" class="ci-computed">
              <span class="status-pill" :class="gerechnet(it).pill">
                {{ gerechnet(it).label }}</span>
              <span class="ci-computed-text">{{ gerechnet(it).text }}</span>
              <span class="ci-lock" title="Dieser Punkt wird aus den Daten der Anwendung
gerechnet und lässt sich nicht von Hand setzen.">🔒 nicht bedienbar</span>
            </div>

            <!-- Kernfrage Art. 3 Nr. 31 — eigener Endpunkt, ja/nein + Begründung -->
            <div v-else-if="it.id === 'wesentliche_aenderung'" class="ci-form">
              <template v-if="canWrite && !detail.vorgang.gesperrt">
                <select v-model="waForm.wert">
                  <option value="">— unbeantwortet —</option>
                  <option value="ja">ja — wesentliche Änderung</option>
                  <option value="nein">nein</option>
                </select>
                <textarea v-model="waForm.grund" rows="2"
                          placeholder="Begründung (auch für „nein“ Pflicht)"></textarea>
                <button class="btn-primary btn-mini" :disabled="busy || !waForm.wert"
                        @click="speichereWa">Speichern</button>
              </template>
              <div class="ci-readonly">
                <span class="status-pill" :class="detail.vorgang.wesentliche_aenderung ? 'erledigt' : 'offen'">
                  {{ detail.vorgang.wesentliche_aenderung || 'unbeantwortet' }}</span>
                <span v-if="detail.vorgang.wesentliche_aenderung_grund" class="ci-computed-text">
                  {{ detail.vorgang.wesentliche_aenderung_grund }}</span>
              </div>
            </div>

            <!-- Entscheidung / gleichbleibend: Status + Begründung -->
            <div v-else class="ci-form">
              <template v-if="canWrite && !detail.vorgang.gesperrt">
                <select v-model="form[it.id].status">
                  <option v-for="s in STATUS" :key="s" :value="s">{{ standLabel(s) }}</option>
                </select>
                <textarea v-model="form[it.id].begruendung" rows="2"
                          :placeholder="begruendungPflicht.includes(it.id)
                            ? 'Begründung (Pflicht, sobald nicht mehr offen)'
                            : 'Begründung / Bestätigung (optional)'"></textarea>
                <button class="btn-primary btn-mini" :disabled="busy"
                        @click="speichereItem(it.id)">Speichern</button>
              </template>
              <div class="ci-readonly">
                <span class="status-pill" :class="stand(it.id).status">
                  {{ standLabel(stand(it.id).status) }}</span>
                <span v-if="stand(it.id).begruendung" class="ci-computed-text">
                  {{ stand(it.id).begruendung }}</span>
                <span v-if="stand(it.id).von" class="ci-ref">{{ stand(it.id).von }}
                  · {{ tag(stand(it.id).am) }}</span>
              </div>
            </div>
            <FehlerHinweis :text="itemMsg[it.id]" />
          </li>
        </ul>
      </div>

      <!-- Offene Punkte — unverändert mit den vorhandenen Sprüngen -->
      <div class="form-card">
        <h4 v-if="detail.gate.offene_punkte.length">Offene Punkte — hier pflegen</h4>
        <ul v-if="detail.gate.offene_punkte.length" class="offen">
          <li v-for="(o, i) in detail.gate.offene_punkte" :key="i">
            <span class="typ">{{ o.typ }}</span>
            <span class="txt">{{ o.titel }}<em v-if="o.hinweis"> — {{ o.hinweis }}</em>
              <span v-if="o.ungeprueft" class="badge soft">ungeprüft</span>
              <span v-if="o.phase === 'release'" class="badge soft">Release-Pflicht</span></span>
            <button v-if="o.link" class="btn-link" @click="$emit('goto', o.link)">
              → hier pflegen</button>
          </li>
        </ul>
        <p v-else class="hint-ok">✔ Keine offenen Punkte — das Release ist bereit.</p>
      </div>

      <!-- Aktionen nach Status UND Rolle (#1743) -->
      <div class="form-card">
        <div class="actions">
          <button v-if="canWrite && ['entwurf', 'zurueckgewiesen'].includes(detail.vorgang.freigabe_status)"
                  class="btn-primary" :disabled="busy" @click="einreichen">
            📤 Zur Prüfung geben</button>
          <template v-if="detail.vorgang.freigabe_status === 'in_pruefung'">
            <button v-if="canApprove" class="btn-primary" :disabled="busy" @click="freigeben">
              ✅ Release freigeben</button>
            <button v-if="canApprove" class="btn-secondary" :disabled="busy"
                    @click="zwOffen = !zwOffen">↩️ Zurückweisen</button>
            <span v-if="!canApprove" class="hint-sub">Wartet auf die Prüfung durch Compliance
              (Berechtigung <code>cra:approve</code>).</span>
          </template>
          <button v-if="canWrite && detail.vorgang.freigabe_status === 'freigegeben'"
                  class="btn-primary" :disabled="busy" @click="veroeffentlichen">
            🚀 Als veröffentlicht markieren</button>
          <span class="sep" />
          <button v-if="canExport" class="btn-secondary" :disabled="busy" @click="download('pdf')">
            📄 Konformitätsnachweis (PDF)</button>
          <button v-if="canExport" class="btn-secondary" :disabled="busy" @click="download('docx')">
            📝 Nachweis (DOCX)</button>
          <button v-if="canExport" class="btn-secondary" :disabled="busy" @click="archivieren">
            📦 Nachweis archivieren</button>
        </div>
        <div v-if="zwOffen && canApprove" class="grund-card">
          <label>Begründung der Zurückweisung (Pflicht)</label>
          <textarea v-model="zwGrund" rows="2"
                    placeholder="Was fehlt, damit das Release freigegeben werden kann?"></textarea>
          <div class="actions">
            <button class="btn-secondary" @click="zwOffen = false">Abbrechen</button>
            <button class="btn-primary" :disabled="busy" @click="zurueckweisen">
              Zurückweisung speichern</button>
          </div>
        </div>
        <FehlerHinweis :text="msg" :art="msgErr ? 'fehler' : 'erfolg'" @close="msg = ''" />
      </div>

      <div v-if="archiv.length" class="form-card">
        <h4>Freigegebene Nachweise (unveränderlich)</h4>
        <ul class="archiv">
          <li v-for="a in archiv" :key="a.id">
            <strong>{{ a.version || '—' }}</strong>
            <span class="status-pill" :class="a.ampel">{{ ampelLabel(a.ampel) }}</span>
            <span class="muted ci-ref">{{ tag(a.freigegeben_am) }} · {{ a.freigegeben_von }} ·
              SHA-256 {{ (a.sha256 || '').slice(0, 12) }}…</span>
            <button class="btn-link" @click="downloadArchiv(a.id)">herunterladen</button>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import apiClient from '../../api/client'
import { useCraStore } from '../../stores/cra'
import { useAuthStore } from '../../stores/auth'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'

const props = defineProps<{ projekt: string; startVersion?: string }>()
defineEmits<{ (e: 'goto', tab: string): void }>()

const store = useCraStore()
const auth = useAuthStore()

/** Rollentrennung (#1743): Entwicklung schreibt, Compliance gibt frei. */
const canWrite = computed(() => auth.hasPermission('cra:write'))
const canApprove = computed(() => auth.hasPermission('cra:approve'))
const canExport = computed(() => auth.hasPermission('cra:export'))

const KONF = '/cra-konformitaet'
const STATUS = ['offen', 'erledigt', 'nicht_anwendbar']

const version = ref('')
const versions = ref<string[]>([])
const repo = ref('')
const provider = ref('')
const detail = ref<any | null>(null)
const archiv = ref<any[]>([])
const begruendungPflicht = ref<string[]>([])
const busy = ref(false)
const err = ref('')
const msg = ref('')
const msgErr = ref(false)
const p1Msg = ref('')
const p1Err = ref(false)
const entzugOffen = ref(false)
const entzugGrund = ref('')
const zwOffen = ref(false)
const zwGrund = ref('')
const itemMsg = reactive<Record<string, string>>({})
const form = reactive<Record<string, { status: string; begruendung: string }>>({})
const waForm = reactive({ wert: '', grund: '' })

const base = () => `${KONF}/projekte/${encodeURIComponent(props.projekt)}`
const craReady = computed(() => store.craReady)

const ampelLabel = (a: string) =>
  ({ gruen: 'KONFORM', bedingt: 'BEDINGT KONFORM', rot: 'NICHT KONFORM' } as any)[a] || a || '—'
const statusLabel = (s: string) => ({
  entwurf: 'Entwurf', in_pruefung: 'in Prüfung', freigegeben: 'freigegeben',
  zurueckgewiesen: 'zurückgewiesen', veroeffentlicht: 'veröffentlicht',
} as any)[s] || s || '—'
const standLabel = (s: string) => ({
  offen: 'offen', erledigt: 'erledigt', nicht_anwendbar: 'nicht anwendbar',
} as any)[s] || s
const tag = (v?: string | null) => (v || '').slice(0, 10)

// ── Phase 1 in einer Zeile ───────────────────────────────────────────────
const phase1Ampel = computed(() => {
  const r = craReady.value
  if (!r || r.status !== 'bereit') return 'rot'
  return r.ueberholt ? 'bedingt' : 'gruen'
})
const phase1Text = computed(() => {
  const r = craReady.value
  if (!r || r.status === 'offen') return 'nicht festgestellt — Produkt zuerst konform machen'
  if (r.status === 'entzogen') {
    return `Feststellung entzogen${r.am ? ` am ${tag(r.am)}` : ''}` +
      (r.entzug_grund ? ` — ${r.entzug_grund}` : '')
  }
  return `festgestellt${r.am ? ` am ${tag(r.am)}` : ''}${r.von ? ` von ${r.von}` : ''}`
})

// ── Checkliste: vier Arten, vier Gruppen ─────────────────────────────────
const GRUPPEN_META: Record<string, { titel: string; badge: string; erklaerung: string }> = {
  gerechnet: {
    titel: 'Gerechnet — Ergebnis aus den Daten der Anwendung',
    badge: '🔒 gerechnet',
    erklaerung: 'Diese Punkte leitet die Anwendung aus ihren Daten ab. Sie sind nicht ' +
      'abhakbar — eine Liste, die sich selbst abhaken ließe, wäre als Nachweis wertlos.',
  },
  entscheidung: {
    titel: 'Entscheidung — jedes Mal zu beantworten, mit Begründung',
    badge: '✍️ Entscheidung',
    erklaerung: 'Das sind die Punkte, die kein Rechenweg kennt. Sie brauchen je Release ' +
      'eine ausdrückliche Antwort und eine Begründung.',
  },
  gleichbleibend: {
    titel: 'Gleichbleibend — je Release nur zu bestätigen',
    badge: '♻️ unverändert',
    erklaerung: 'Einmal gesetzte Angaben, die aus ihrer Quelle gelesen werden. Die ' +
      'Bestätigung hält fest, dass jemand hingesehen hat.',
  },
  // #1755: Erscheint nur bei „wesentliche Änderung: ja". Diese vier Punkte
  // sind der Grund, warum die Frage überhaupt gestellt wird.
  neubewertung: {
    titel: 'Neubewertung — ausgelöst durch die wesentliche Änderung',
    badge: '⚠️ Neubewertung',
    erklaerung: 'Eine wesentliche Änderung (Art. 3 Nr. 31) löst die ' +
      'Konformitätsbewertung erneut aus und verlangt, die Risikoabschätzung ' +
      'fortzuschreiben. Offene Punkte hier machen das Release rot — das ist ' +
      'keine Lücke in der Akte, sondern eine Nicht-Konformität.',
  },
}
const gruppen = computed(() => {
  const katalog: any[] = detail.value?.katalog || []
  // Die Neubewertungs-Gruppe wird nur gezeigt, wenn die wesentliche Änderung
  // bejaht wurde — sonst stünden dort vier Punkte, die niemanden betreffen,
  // und die Liste verlöre ihre Aussagekraft.
  const wesentlich = detail.value?.vorgang?.wesentliche_aenderung === 'ja'
  const arten = ['gerechnet', 'entscheidung', 'gleichbleibend']
  if (wesentlich) arten.push('neubewertung')
  return arten
    .map(art => ({ art, ...GRUPPEN_META[art], items: katalog.filter(i => i.art === art) }))
    .filter(g => g.items.length)
})

const stand = (id: string) =>
  (detail.value?.stand || {})[id] || { status: 'offen', begruendung: '', von: '', am: '' }

/**
 * Darstellung eines gerechneten Punktes aus dem Gate — **keine** zweite
 * Rechnung: `quelle` nennt den flachen Schlüssel, unter dem
 * `konformitaet_gate.evaluate` das Ergebnis liefert. `null` heißt dort
 * ausdrücklich „nicht geprüft"; das wird auch so angezeigt und nicht zu 0
 * verharmlost (#1741).
 */
function gerechnet(item: any): { pill: string; label: string; text: string } {
  const g = detail.value?.gate || {}
  const ok = (text: string) => ({ pill: 'erledigt', label: 'erfüllt', text })
  const bad = (text: string) => ({ pill: 'rot', label: 'offen', text })
  // Drei verschiedene Aussagen, die vorher alle „nicht geprüft" hießen:
  //   • Die Quelle ließ sich nicht lesen  → nicht geprüft (das Gate meldet dazu
  //     einen Punkt mit `ungeprueft`).
  //   • Die Grundlage fehlt (z. B. kein Support-Zeitraum erfasst) → nicht
  //     bestimmbar, mit dem Klartext des offenen Punktes.
  //   • Alles andere ist erfüllt oder offen.
  // „Datenquelle nicht auswertbar" für einen schlicht nicht erfassten Wert zu
  // drucken, behauptet einen technischen Fehler, wo eine Eingabe fehlt.
  const punkte = ([] as any[]).concat(g.release_punkte || [], g.produkt_punkte || [])
  const TYP: Record<string, string> = {
    offene_kritische_schwachstellen: 'schwachstelle', behobene_ohne_advisory: 'advisory',
    sbom_version_fehlt: 'sbom', support_ueberschritten: 'support',
    ueberfaellige_meldungen: 'meldefrist', annex_vollstaendig: 'annex',
    doc_ausgestellt: 'doc',
    bewertungsweg_unzulaessig: 'bewertungsweg',
    // #1761
    fremdkomponenten_unbewertet: 'fremdkomponenten',
    upstream_meldung_offen: 'upstream_meldung',
    // #1774
    komponenten_befund_widerspruch: 'komponenten_befunde',
    // #1762
    update_zusagen_fehlen: 'update_zusage',
    kaufhinweis_fehlt: 'update_zusage',
    aufbewahrungsfristen_unbestimmbar: 'aufbewahrung',
    marktaufsicht_versaeumt: 'marktaufsicht',
  }
  const typ = TYP[item.quelle] || ''
  const unk = () => {
    const ungeprueft = punkte.find((p: any) => p.ungeprueft && p.typ === typ)
    if (ungeprueft) {
      return { pill: 'fehlt', label: 'nicht geprüft',
               text: ungeprueft.hinweis || 'Die Datenquelle war nicht auswertbar.' }
    }
    const offen = punkte.find((p: any) => p.typ === typ)
    return { pill: 'fehlt', label: 'nicht bestimmbar',
             text: offen ? `${offen.titel}${offen.hinweis ? ' — ' + offen.hinweis : ''}`
                         : 'Grundlage fehlt — bitte erfassen.' }
  }
  const v = g[item.quelle]
  switch (item.quelle) {
    case 'offene_kritische_schwachstellen':
      return v === 0 ? ok('Keine offenen kritischen oder hohen Befunde.')
        : bad(`${v} offene kritische/hohe Schwachstelle(n).`)
    case 'behobene_ohne_advisory':
      if (v == null) return unk()
      return v.length === 0 ? ok('Jede in dieser Version behobene Schwachstelle trägt ein Advisory.')
        : bad(`${v.length} ohne Advisory: ${v.slice(0, 5).join(', ')}`)
    case 'sbom_version_fehlt':
      if (v == null) return unk()
      return v ? bad('Keine SBOM zu dieser Release-Version.') : ok('SBOM zur Version liegt vor.')
    case 'support_ueberschritten':
      if (v == null) return unk()
      return v ? bad('Das zugesagte Support-Ende ist überschritten.')
        : ok('Release liegt im zugesagten Support-Zeitraum.')
    case 'ueberfaellige_meldungen': {
      if (v == null) return unk()
      // Das Gate liefert eine **Liste** der überfälligen Stufen. Der Vergleich
      // gegen 0 traf nie zu, also meldete die Oberfläche bei einer leeren Liste
      // „offen — überfällige Meldefrist(en)" — ein behaupteter Rechtsverstoß,
      // den es nicht gab.
      const n = Array.isArray(v) ? v.length : (Number(v) || 0)
      return n === 0 ? ok('Keine überfällige Meldefrist.')
        : bad(`${n} überfällige Meldefrist(en).`)
    }
    case 'bewertungsweg_unzulaessig':
      // #1759: Mangel-Flag — `true` heißt „unzulässig". Ohne eigenen Zweig
      // fiele der Punkt in `unk()` und zeigte „nicht bestimmbar" statt des
      // Befundes, der die Ampel rot macht.
      if (v == null) return unk()
      return v ? bad('Der Bewertungsweg ist für diese Produktklasse nicht zulässig.')
        : ok('Bewertungsweg für die Produktklasse zulässig.')
    case 'fremdkomponenten_unbewertet': {
      // #1761: Liste der neu aufgenommenen oder angehobenen Fremdkomponenten
      // ohne Bewertung. `null` heißt „keine Komponentenliste zur SBOM" — dann
      // ist die Sorgfaltspflicht nicht belegbar, und `unk()` druckt den Satz
      // des offenen Punktes, der genau das sagt.
      if (v == null) return unk()
      const n = Array.isArray(v) ? v.length : (Number(v) || 0)
      return n === 0 ? ok('Neue und angehobene Fremdkomponenten sind bewertet.')
        : bad(`${n} ohne Bewertung: ${(Array.isArray(v) ? v : []).slice(0, 5).join(', ')}`)
    }
    // #1774: Widerspruch zwischen der Bewertung einer Fremdkomponente und dem
    // eigenen offenen Befund gegen sie. `null` heißt „keine Komponentenliste" —
    // dann ist nichts zu vergleichen, und `unk()` sagt das.
    case 'komponenten_befund_widerspruch': {
      if (v == null) return unk()
      const n = Array.isArray(v) ? v.length : (Number(v) || 0)
      return n === 0
        ? ok('Keine Bewertung widerspricht einem offenen Befund.')
        : bad(`${n} als „nicht relevant“ bewertet trotz offenem Befund: `
              + `${(Array.isArray(v) ? v : []).slice(0, 5).join(', ')}`)
    }
    case 'upstream_meldung_offen': {
      if (v == null) return unk()
      const n = Array.isArray(v) ? v.length : (Number(v) || 0)
      return n === 0
        ? ok('Eigene Funde in Fremdkomponenten sind deren Herstellern gemeldet.')
        : bad(`${n} ohne dokumentierte Meldung: `
              + `${(Array.isArray(v) ? v : []).slice(0, 5).join(', ')}`)
    }
    // #1762: Mangel-Kennzeichen — true heißt „fehlt", nicht „erfüllt".
    case 'update_zusagen_fehlen':
      if (v == null) return unk()
      return v ? bad('Update-Zusagen nicht vollständig dokumentiert.')
               : ok('Sicherheitsupdates kostenlos und über getrennten Kanal zugesagt.')
    case 'kaufhinweis_fehlt':
      if (v == null) return unk()
      return v ? bad('Kein Hinweis auf das Support-Ende beim Kauf.')
               : ok('Support-Ende ist vor dem Kauf zugänglich.')
    case 'aufbewahrungsfristen_unbestimmbar':
      if (v == null) return unk()
      return v ? bad('Aufbewahrungs-/Update-Fristen nicht bestimmbar — Bezugsdaten fehlen.')
               : ok('Aufbewahrungs- und Update-Fristen sind bestimmbar.')
    case 'marktaufsicht_versaeumt': {
      if (v == null) return unk()
      const n = Number(v) || 0
      return n === 0
        ? ok('Keine versäumte Frist gegenüber der Marktüberwachung.')
        : bad(`${n} versäumte Frist(en) gegenüber der Marktüberwachung.`)
    }
    case 'annex_vollstaendig':
      return v ? ok('Technische Dokumentation vollständig.') : bad('Annex-VII-Bausteine fehlen.')
    case 'doc_ausgestellt':
      return v ? ok('EU-Konformitätserklärung ausgestellt.') : bad('DoC nicht ausgestellt.')
    default:
      return unk()
  }
}

// ── Laden ────────────────────────────────────────────────────────────────
async function loadVersions() {
  try {
    const d = (await apiClient.get(`${base()}/versions`)).data || {}
    versions.value = d.versions || []; repo.value = d.repo || ''; provider.value = d.provider || ''
  } catch { /* optional — Version lässt sich auch tippen */ }
}

async function loadUmfeld() {
  await store.fetchReleases()
  try { await store.fetchCraReady() } catch { /* Phase-1-Zeile bleibt auf dem Listen-Stand */ }
  try {
    const k = await store.fetchReleaseKatalog()
    begruendungPflicht.value = k.begruendung_pflicht || []
  } catch { /* Katalog kommt auch mit dem Detail */ }
  try { archiv.value = (await apiClient.get(`${base()}/nachweis/archiv`)).data?.eintraege || [] }
  catch { archiv.value = [] }
}

/** Die geöffnete Version — auch dann, wenn es dafür noch keinen Vorgang gibt. */
const offeneVersion = computed(() => version.value)

/** Vorgang ausdrücklich anlegen und danach öffnen. */
async function anlegen() {
  const ver = (version.value || '').trim()
  if (!ver) return
  busy.value = true; err.value = ''
  try {
    await store.releaseAnlegen(ver)
    await store.fetchReleases()
    await oeffnen(ver)
    msg.value = `Vorgang für ${ver} angelegt.`
  } catch (e: any) {
    err.value = e?.response?.data?.error || 'Vorgang konnte nicht angelegt werden.'
  } finally { busy.value = false }
}

async function oeffnen(v: string) {
  const ver = (v || '').trim()
  if (!ver) return
  busy.value = true; err.value = ''; msg.value = ''; zwOffen.value = false
  try {
    version.value = ver
    detail.value = await store.fetchReleaseDetail(ver)
    Object.keys(itemMsg).forEach(k => delete itemMsg[k])
    for (const it of detail.value.katalog || []) {
      const s = stand(it.id)
      form[it.id] = { status: s.status || 'offen', begruendung: s.begruendung || '' }
    }
    waForm.wert = detail.value.vorgang?.wesentliche_aenderung || ''
    waForm.grund = detail.value.vorgang?.wesentliche_aenderung_grund || ''
  } catch (e: any) {
    detail.value = null
    err.value = e?.response?.data?.error || 'Vorgang konnte nicht geladen werden.'
  } finally { busy.value = false }
}

/** Nach jedem Schreibvorgang: Vorgang + Liste neu, damit Status und Ampel stimmen. */
async function nachSchreiben() {
  const v = version.value
  await store.fetchReleases()
  if (v) await oeffnen(v)
}

function fehler(e: any, fallback: string) {
  // Regelverletzungen kommen als 409 mit erklärendem Klartext — den zeigen wir
  // wörtlich. Eine eigene Formulierung wäre kürzer und falscher.
  return e?.response?.data?.error || fallback
}

// ── Schreiben: Checkliste ────────────────────────────────────────────────
async function speichereItem(id: string) {
  busy.value = true; delete itemMsg[id]
  try {
    await store.setReleaseChecklistItem(version.value, id,
      form[id].status, form[id].begruendung)
    detail.value = await store.fetchReleaseDetail(version.value)
  } catch (e: any) { itemMsg[id] = fehler(e, 'Speichern fehlgeschlagen.') }
  finally { busy.value = false }
}

async function speichereWa() {
  busy.value = true; delete itemMsg['wesentliche_aenderung']
  try {
    await store.setWesentlicheAenderung(version.value, waForm.wert, waForm.grund)
    detail.value = await store.fetchReleaseDetail(version.value)
  } catch (e: any) { itemMsg['wesentliche_aenderung'] = fehler(e, 'Speichern fehlgeschlagen.') }
  finally { busy.value = false }
}

// ── Schreiben: Statusmaschine ────────────────────────────────────────────
async function lauf(fn: () => Promise<any>, ok: string) {
  busy.value = true; msg.value = ''; msgErr.value = false
  try {
    await fn()
    msg.value = ok
    await nachSchreiben()
  } catch (e: any) { msg.value = fehler(e, 'Aktion fehlgeschlagen.'); msgErr.value = true }
  finally { busy.value = false }
}

const einreichen = () => lauf(() => store.releaseEinreichen(version.value),
  'Zur Prüfung gegeben — der gerechnete Stand ist eingefroren.')
const freigeben = () => lauf(() => store.releaseFreigeben(version.value),
  'Release freigegeben.')
const veroeffentlichen = () => lauf(() => store.releaseVeroeffentlichen(version.value),
  'Als veröffentlicht vermerkt.')
async function zurueckweisen() {
  await lauf(() => store.releaseZurueckweisen(version.value, zwGrund.value), 'Zurückgewiesen.')
  if (!msgErr.value) { zwOffen.value = false; zwGrund.value = '' }
}

// ── Phase 1 schreiben ────────────────────────────────────────────────────
async function feststellen() {
  busy.value = true; p1Msg.value = ''; p1Err.value = false
  try {
    await store.craReadyFeststellen()
    await store.fetchCraReady()
    p1Msg.value = 'CRA-ready festgestellt.'
  } catch (e: any) { p1Msg.value = fehler(e, 'Feststellung fehlgeschlagen.'); p1Err.value = true }
  finally { busy.value = false }
}

async function entziehen() {
  busy.value = true; p1Msg.value = ''; p1Err.value = false
  try {
    await store.craReadyEntziehen(entzugGrund.value)
    await store.fetchCraReady()
    p1Msg.value = 'Feststellung entzogen.'
    entzugOffen.value = false; entzugGrund.value = ''
  } catch (e: any) { p1Msg.value = fehler(e, 'Entzug fehlgeschlagen.'); p1Err.value = true }
  finally { busy.value = false }
}

// ── Nachweis ─────────────────────────────────────────────────────────────
function oeffneBlob(data: Blob) {
  const url = URL.createObjectURL(data)
  window.open(url, '_blank', 'noopener'); setTimeout(() => URL.revokeObjectURL(url), 60000)
}

async function download(fmt: string) {
  try {
    const r = await apiClient.get(`${base()}/nachweis`, {
      params: { version: version.value || undefined, format: fmt }, responseType: 'blob' })
    oeffneBlob(r.data as Blob)
  } catch (e: any) { msg.value = fehler(e, 'Download fehlgeschlagen.'); msgErr.value = true }
}

async function downloadArchiv(id: number) {
  try {
    const r = await apiClient.get(`${base()}/nachweis/archiv/${id}/download`, { responseType: 'blob' })
    oeffneBlob(r.data as Blob)
  } catch { msg.value = 'Download fehlgeschlagen.'; msgErr.value = true }
}

async function archivieren() {
  if (!confirm(`Konformitätsnachweis für „${version.value}“ unveränderlich archivieren?`)) return
  busy.value = true; msg.value = ''; msgErr.value = false
  try {
    const r = await apiClient.post(`${base()}/nachweis/freigeben`, { version: version.value })
    msg.value = `Archiviert (SHA-256 ${String(r.data.sha256).slice(0, 12)}…).`
  } catch (e: any) {
    const d = e?.response?.data
    if (e?.response?.status === 428 && d?.error === 'release_rot') {
      if (confirm('Release ist NICHT konform (offene Punkte). Trotzdem als bedingte Freigabe archivieren?')) {
        const r = await apiClient.post(`${base()}/nachweis/freigeben`,
          { version: version.value, confirm_rot: true })
        msg.value = `Bedingt archiviert (SHA-256 ${String(r.data.sha256).slice(0, 12)}…).`
      }
    } else { msg.value = fehler(e, 'Archivieren fehlgeschlagen.'); msgErr.value = true }
  } finally {
    busy.value = false
    try { archiv.value = (await apiClient.get(`${base()}/nachweis/archiv`)).data?.eintraege || [] }
    catch { /* Liste bleibt */ }
  }
}

watch(() => props.projekt, async () => {
  detail.value = null; version.value = ''; err.value = ''; msg.value = ''; p1Msg.value = ''
  await loadVersions()
  await loadUmfeld()
  // Deep-Link ?tab=releases&version=… landet direkt im Vorgang.
  const ziel = (props.startVersion || '').trim()
  if (ziel) await oeffnen(ziel)
}, { immediate: true })

watch(() => props.startVersion, (v) => { if (v && v !== version.value) oeffnen(v) })
</script>

<style scoped>
.panel-header h3 { color: #1565c0; margin-bottom: 4px; }
.panel-header .sub { color: #607d8b; font-size: 13px; margin: 0; max-width: 820px; }
.form-card { background: #f5f8fc; border: 1px solid #cfd8e3; border-radius: 8px; padding: 16px; margin: 12px 0; }
h4 { color: #1565c0; margin: 0 0 6px; font-size: 14px; }
.hint-sub { font-size: 12px; color: #607d8b; margin: 4px 0 0; }
.hint-ok { color: #2e7d32; margin: 0; }
.muted { color: #90a4ae; }
.alert { border-radius: 6px; padding: 8px 12px; font-size: 13px; margin: 8px 0 0; }
.alert-error { background: #ffebee; color: #c62828; border: 1px solid #ffcdd2; }
.alert-ok { background: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9; }
.alert.inline { margin: 6px 0 0; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; padding: 0; font-size: 13px; }
.btn-mini { padding: 4px 10px; font-size: 12px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 8px; }
.actions .sep { flex: 1 1 0; min-width: 0; }
.ver-input { display: flex; gap: 8px; align-items: center; }
.ver-input input { padding: 6px 10px; border: 1px solid #cfd8e3; border-radius: 6px; min-width: 200px; }
.card-head { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; justify-content: space-between; }
.grund-card label { display: block; font-size: 12px; color: #455a64; margin-bottom: 4px; }
textarea, select { width: 100%; max-width: 640px; padding: 6px 10px; border: 1px solid #cfd8e3;
  border-radius: 6px; font-size: 13px; font-family: inherit; box-sizing: border-box; }
select { max-width: 280px; }

/* Phase 1 — genau eine Zeile */
.phase1 {
  display: flex; align-items: center; gap: 10px; flex-wrap: nowrap;
  background: white; border: 1px solid #cfd8e3; border-left: 5px solid #9e9e9e;
  border-radius: 8px; padding: 8px 14px; margin: 12px 0; font-size: 13px; overflow: hidden;
}
.phase1.gruen { border-left-color: #2e7d32; }
.phase1.bedingt { border-left-color: #f57f17; }
.phase1.rot { border-left-color: #c62828; }
.phase1 .dot { width: 11px; height: 11px; border-radius: 50%; background: #9e9e9e; flex: none; }
.phase1.gruen .dot { background: #2e7d32; }
.phase1.bedingt .dot { background: #f57f17; }
.phase1.rot .dot { background: #c62828; }
.p1-label { color: #1a237e; flex: none; }
.p1-text { color: #455a64; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.p1-warn { color: #ef6c00; white-space: nowrap; flex: none; }
.p1-spacer { flex: 1 1 0; min-width: 8px; }
.phase1 button { flex: none; white-space: nowrap; }
.grund-card { margin-top: 0; }

/* Ampel des Vorgangs — wie im bisherigen Release-Check */
.ampel-card { display: flex; flex-direction: column; gap: 8px; border-left: 5px solid #9e9e9e; }
.ampel-card.gruen { border-left-color: #2e7d32; }
.ampel-card.bedingt { border-left-color: #f57f17; }
.ampel-card.rot { border-left-color: #c62828; }
.ampel-top { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.ampel-top strong { font-size: 15px; color: #1a237e; }
.ampel-top .pct { color: #607d8b; font-size: 13px; }
.ampel-card .dot { width: 13px; height: 13px; border-radius: 50%; background: #9e9e9e; }
.ampel-card.gruen .dot { background: #2e7d32; }
.ampel-card.bedingt .dot { background: #f57f17; }
.ampel-card.rot .dot { background: #c62828; }
.counts { display: flex; gap: 10px; flex-wrap: wrap; font-size: 12.5px; }
.counts span { padding: 2px 9px; border-radius: 10px; background: #eceff1; color: #455a64; }
.counts .ok { background: #e8f5e9; color: #2e7d32; }
.counts .warn { background: #fff8e1; color: #ef6c00; }
.counts .bad { background: #ffebee; color: #c62828; }
.rejected { background: #ffebee; color: #c62828; border-radius: 6px; padding: 8px 12px; font-size: 13px; }

/* Status-Pillen wie im Dokumenten-Register */
.status-pill { padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;
  background: #eceff1; color: #607d8b; white-space: nowrap; }
.status-pill.entwurf, .status-pill.offen, .status-pill.fehlt { background: #eceff1; color: #607d8b; }
.status-pill.in_pruefung { background: #fff8e1; color: #e65100; }
.status-pill.zurueckgewiesen, .status-pill.rot { background: #ffebee; color: #c62828; }
.status-pill.freigegeben, .status-pill.erledigt, .status-pill.gruen { background: #e8f5e9; color: #2e7d32; }
.status-pill.veroeffentlicht, .status-pill.nicht_anwendbar { background: #e3f2fd; color: #1565c0; }
.status-pill.bedingt { background: #fff8e1; color: #ef6c00; }

/* Die drei Arten unterscheiden sich durch Gruppenüberschrift + Badge-Text,
   nicht durch Farbe: Farbe bleibt dem Erfüllungsgrad vorbehalten (#1727). */
.badge { font-size: 10.5px; font-weight: 600; letter-spacing: .3px; padding: 2px 8px;
  border-radius: 4px; background: #eceff1; color: #455a64; border: 1px solid #cfd8e3;
  white-space: nowrap; }
.badge.art { min-width: 104px; text-align: center; }
.badge.soft { font-weight: 500; background: white; }

/* Release-Liste */
ul.rel-list, ul.check-list, ul.offen, ul.archiv { list-style: none; padding: 0; margin: 8px 0 0; }
ul.rel-list li { display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
  padding: 7px 8px; border-bottom: 1px solid #e6ecf3; cursor: pointer; border-radius: 6px; }
ul.rel-list li:last-child { border-bottom: none; }
ul.rel-list li:hover { background: #eaf2fb; }
ul.rel-list li.active { background: #e3f2fd; }
.rl-ver { min-width: 92px; color: #1a237e; }
.rl-meta { font-size: 12px; color: #607d8b; flex: 1; }

/* Checkliste */
ul.check-list li { padding: 10px 0; border-bottom: 1px solid #e6ecf3; }
ul.check-list li:last-child { border-bottom: none; }
ul.check-list li.computed { opacity: .96; }
.ci-head { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.ci-label { font-weight: 600; color: #263238; font-size: 13px; }
.ci-ref { font-size: 11px; color: #78909c; }
.ci-text { font-size: 12px; color: #546e7a; margin: 4px 0 6px; max-width: 820px; }
.ci-computed { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap;
  background: white; border: 1px dashed #cfd8e3; border-radius: 6px; padding: 6px 10px; }
.ci-computed-text { font-size: 12.5px; color: #455a64; }
.ci-lock { font-size: 11px; color: #90a4ae; margin-left: auto; white-space: nowrap; }
.ci-form { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }
.ci-readonly { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }

ul.offen li { display: flex; gap: 10px; align-items: baseline; padding: 6px 0;
  border-bottom: 1px solid #e6ecf3; }
ul.offen li:last-child { border-bottom: none; }
ul.offen .typ { font-size: 10.5px; color: #607d8b; min-width: 96px; text-transform: uppercase;
  letter-spacing: .4px; }
ul.offen .txt { flex: 1; }
ul.archiv li { display: flex; gap: 10px; align-items: baseline; padding: 5px 0; }
</style>
