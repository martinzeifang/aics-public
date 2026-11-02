<!--
  IssueVerknuepfung (#1847) — der Issue-Baustein für alle sechs Module.

  DER BEFUND
  ~350 Zeilen Issue-Bedienung in fünf Masken, keine geteilte Komponente. Was
  dabei auseinanderlief, war nicht nur die Beschriftung: „Issue anlegen" gab
  es in vier Fassungen **mit** Provider-/Repo-/Titel-/Body-Formular (nur
  `RequirementActions`) und drei Fassungen, die ohne Rückfrage direkt
  anlegten; „Bestehendes verknüpfen" fehlte in drei Masken ganz; ein
  Entknüpfen-Knopf fehlte in CRA, obwohl die Store-Funktion dafür existierte
  und ungenutzt dalag.

  WARUM DAS JETZT GEHT
  Erst seit #1846 hat jede Objektart dieselbe Routenform
  (`…/<pfad>/<id>/issues[/link|/sync|/<link_id>]`, `…/<pfad>/<id>/import-issue`).
  Vorher hätte die Komponente Fähigkeitslücken kennen müssen — und eine
  Komponente mit einer Tabelle „welches Modul kann was" ist keine geteilte.

  WAS PARAMETRISIERT IST UND WARUM
  `textZiel` nennt den Freitext, in den die Übernahme schreibt: Kommentar
  (Anforderungen), Notiz (WiBA), Bemerkung (Risiken), Triage-Kommentar
  (Schwachstellen). Das ist kein Schönheitsfehler, den man wegvereinheitlicht
  — der Anwender muss wissen, wohin der Text geht, und das Feld heißt in
  seiner Maske so.

  `darstellung="zeile"` ist die kompakte Form für Tabellenzellen (CRAs Risiken
  und Schwachstellen). Dieselben Handlungen, dieselben Endpunkte, nur als
  Symbolknöpfe mit dem Titel-Text aus dem Katalog — eine Tabellenzeile trägt
  kein Fieldset mit drei Knopfreihen.

  ABWEICHUNG VON #1848, BEWUSST: Die Übernahme (📥) sitzt hier und nicht im
  KI-Baustein. Sie ist keine KI-Handlung — sie schreibt Issue-Text in den
  Freitext und ändert die Bewertung nicht (#1526) —, und CRAs Schwachstellen
  brauchen sie in einer Maske, die überhaupt keinen KI-Pfad hat.
-->
<template>
  <!-- ── Kompakte Form für Tabellenzellen ────────────────────────────── -->
  <span v-if="darstellung === 'zeile'" class="iv-zeile">
    <a v-for="i in issues" :key="i.id" class="iv-pille" :class="i.state || 'open'"
       :href="safeUrl(i.url)" target="_blank" rel="noopener noreferrer"
       :title="`${i.provider} ${nummer(i)} — ${i.title || ''} (${i.state || 'open'})`">
      {{ nummer(i) }}
    </a>
    <button class="iv-symbol" type="button" :disabled="!!busy"
            :title="A.issueAnlegen.titel" @click="oeffneAnlegen">🐙</button>
    <button v-if="issues.length" class="iv-symbol" type="button" :disabled="!!busy"
            :title="A.issueAbgleichen.titel" @click="abgleichen">🔄</button>
    <button class="iv-symbol" type="button" :disabled="!!busy"
            :title="A.issueVerknuepfen.titel" @click="oeffneVerknuepfen">🔗</button>
    <button v-if="mitUebernahme && issues.length" class="iv-symbol" type="button"
            :disabled="!!busy" :title="A.issueImportieren.titel"
            @click="oeffneUebernahme">📥</button>
    <button v-for="i in issues" :key="`x-${i.id}`" class="iv-symbol iv-weg"
            type="button" :disabled="!!busy" :title="A.issueEntknuepfen.titel"
            @click="entknuepfen(i.id)">✕</button>
  </span>

  <!-- ── Blockform (Editor-Masken) ───────────────────────────────────── -->
  <fieldset v-else class="iv-block">
    <legend>{{ ABSCHNITTE.issues }}</legend>
    <div v-if="issues.length === 0" class="iv-leer">Keine Issues verknüpft.</div>
    <div v-else class="iv-liste">
      <div v-for="i in issues" :key="i.id" class="iv-eintrag">
        <span class="iv-status" :class="i.state || 'open'">{{ i.state || 'open' }}</span>
        <a :href="safeUrl(i.url)" target="_blank" rel="noopener noreferrer" class="iv-link">
          {{ i.provider }}{{ nummer(i) }} – {{ i.title || '(ohne Titel)' }}
        </a>
        <button class="iv-symbol iv-weg" type="button" :disabled="!!busy"
                :title="A.issueEntknuepfen.titel"
                @click="entknuepfen(i.id)">{{ A.issueEntknuepfen.text }}</button>
      </div>
    </div>
    <div class="iv-knoepfe">
      <button class="iv-knopf" type="button" :disabled="!!busy"
              :title="A.issueAnlegen.titel" @click="oeffneAnlegen">
        {{ knopf(A.issueAnlegen, busy === 'anlegen') }}
      </button>
      <button class="iv-knopf" type="button" :disabled="!!busy"
              :title="A.issueVerknuepfen.titel" @click="oeffneVerknuepfen">
        {{ knopf(A.issueVerknuepfen, busy === 'verknuepfen') }}
      </button>
      <button class="iv-knopf" type="button" :disabled="!!busy || issues.length === 0"
              :title="A.issueAbgleichen.titel" @click="abgleichen">
        {{ knopf(A.issueAbgleichen, busy === 'abgleichen') }}
      </button>
      <button v-if="mitUebernahme" class="iv-knopf" type="button" :disabled="!!busy"
              :title="A.issueImportieren.titel" @click="oeffneUebernahme">
        {{ knopf(A.issueImportieren, busy === 'uebernehmen') }}
      </button>
      <slot name="knoepfe" />
    </div>
    <FehlerHinweis :text="fehler" @close="fehler = ''" />
  </fieldset>

  <!-- ── Issue anlegen ────────────────────────────────────────────────── -->
  <ModalRahmen v-if="anlegen.open" :titel="`${A.issueAnlegen.text} — ${objektTitel}`"
               @close="anlegen.open = false">
    <template #inhalt>
      <!-- Provider und Repository sind **Überschreibungen**, keine Pflichtfelder.
           Der Server löst beides aus der Repo-Konfiguration des Projekts auf
           (`shared.issue_api.loese_repo`). Ein fest mitgesendetes
           `provider: 'github'` würde ein Projekt überstimmen, das auf GitLab
           konfiguriert ist — und das sähe wie eine Entscheidung des Anwenders
           aus. Leer heißt deshalb: wie im Projekt hinterlegt. -->
      <div class="iv-feld">
        <label :for="`iv-prov-${lauf}`">Provider</label>
        <select :id="`iv-prov-${lauf}`" v-model="anlegen.provider">
          <option value="">(aus der Projekt-Konfiguration)</option>
          <option value="github">GitHub</option>
          <option value="gitlab">GitLab</option>
        </select>
      </div>
      <div class="iv-feld">
        <label :for="`iv-repo-${lauf}`">Repository</label>
        <input :id="`iv-repo-${lauf}`" v-model="anlegen.repo"
               placeholder="(aus der Projekt-Konfiguration)" />
        <small>
          Leer lassen, um das im Projekt hinterlegte Repository zu verwenden.
        </small>
      </div>
      <div class="iv-feld">
        <label :for="`iv-titel-${lauf}`">Titel</label>
        <input :id="`iv-titel-${lauf}`" v-model="anlegen.titel"
               placeholder="(leer: wird aus dem Objekt erzeugt)" />
      </div>
      <div class="iv-feld">
        <label :for="`iv-body-${lauf}`">Beschreibung</label>
        <textarea :id="`iv-body-${lauf}`" v-model="anlegen.body" rows="4"
                  placeholder="(leer: wird aus dem Objekt erzeugt)"></textarea>
      </div>
      <FehlerHinweis :text="anlegen.fehler" @close="anlegen.fehler = ''" />
      <div v-if="anlegen.erzeugt" class="iv-erfolg">
        ✅ <a :href="safeUrl(anlegen.erzeugt.url)" target="_blank"
              rel="noopener noreferrer">{{ anlegen.erzeugt.url }}</a>
      </div>
    </template>
    <template #fuss>
      <button class="iv-sekundaer" type="button" @click="anlegen.open = false">Schließen</button>
      <button class="iv-primaer" type="button"
              :disabled="busy === 'anlegen'" @click="legeAn">
        {{ knopf(A.issueAnlegen, busy === 'anlegen') }}
      </button>
    </template>
  </ModalRahmen>

  <!-- ── Bestehendes verknüpfen ──────────────────────────────────────── -->
  <ModalRahmen v-if="verknuepfen.open" :titel="A.issueVerknuepfen.text"
               breite="schmal" @close="verknuepfen.open = false">
    <template #inhalt>
      <div class="iv-feld">
        <label :for="`iv-url-${lauf}`">Issue-URL *</label>
        <input :id="`iv-url-${lauf}`" v-model="verknuepfen.url"
               placeholder="https://github.com/owner/repo/issues/123"
               @keyup.enter="verknuepfe" />
        <small>Provider und Issue-Nummer werden aus der Adresse erkannt.</small>
      </div>
      <div class="iv-feld">
        <label :for="`iv-vtitel-${lauf}`">Titel (optional)</label>
        <input :id="`iv-vtitel-${lauf}`" v-model="verknuepfen.titel" />
      </div>
      <FehlerHinweis :text="verknuepfen.fehler" @close="verknuepfen.fehler = ''" />
    </template>
    <template #fuss>
      <button class="iv-sekundaer" type="button" @click="verknuepfen.open = false">Abbrechen</button>
      <button class="iv-primaer" type="button"
              :disabled="!verknuepfen.url.trim() || busy === 'verknuepfen'" @click="verknuepfe">
        {{ knopf(A.issueVerknuepfen, busy === 'verknuepfen') }}
      </button>
    </template>
  </ModalRahmen>

  <!-- ── Issue-Inhalt übernehmen (score-neutral, #1526) ──────────────── -->
  <ModalRahmen v-if="uebernahme.open" :titel="`${A.issueImportieren.text} — ${objektTitel}`"
               @close="uebernahme.open = false">
    <template #inhalt>
      <p class="iv-vorbehalt">
        Übernimmt Issue-Inhalt und Review-Feedback in <strong>{{ textZiel }}</strong> —
        die Bewertung wird <strong>nicht</strong> geändert.
      </p>
      <button v-if="issues.length > 0" class="iv-knopf" type="button" :disabled="!!busy"
              style="margin-bottom: 8px" @click="uebernimmAusVerknuepften">
        {{ busy === 'uebernehmen' ? A.issueImportieren.laufend
          : '🔗 Aus verknüpften Issues laden & übernehmen' }}
      </button>
      <textarea v-model="uebernahme.text" rows="9"
                placeholder="Issue-Beschreibung, Kommentare, Review-Feedback hier einfügen…"></textarea>
      <FehlerHinweis :text="uebernahme.fehler" @close="uebernahme.fehler = ''" />
    </template>
    <template #fuss>
      <button class="iv-sekundaer" type="button" @click="uebernahme.open = false">Abbrechen</button>
      <button class="iv-primaer" type="button"
              :disabled="!uebernahme.text.trim() || !!busy" @click="uebernimmText">
        In {{ textZiel }} einfügen
      </button>
    </template>
  </ModalRahmen>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import apiClient from '../../api/client'
import { safeUrl } from '../../utils/safeUrl'
import { ABSCHNITTE, OBJEKT_AKTIONEN as A, knopf } from '../../utils/aktionen'
import FehlerHinweis from './FehlerHinweis.vue'
import ModalRahmen from './ModalRahmen.vue'

const props = withDefaults(defineProps<{
  /** Modul-Prefix: `/cra`, `/nis2`, `/aiact`, `/dsgvo`, `/wiba`, `/risikobewertung`. */
  apiBase: string
  projektName: string
  /** Objekt-Pfad der Fabrik: `anforderungen` | `owasp` | `owasp-llm` | `controls` | `risiken` | `vulns`. */
  objektPfad: string
  objektId: string | number
  /** Für die Modal-Überschrift — die Kennung genügt, der ganze Titel wird zu lang. */
  objektTitel?: string
  /** Vorbelegung des Repository-Feldes aus dem Projekt-Meta. */
  repoVorschlag?: string
  /** Wie der Freitext in dieser Maske heißt (wohin die Übernahme schreibt). */
  textZiel?: string
  /** Die Übernahme anzeigen. Aus, wo das Objekt keinen Freitext hat. */
  mitUebernahme?: boolean
  darstellung?: 'block' | 'zeile'
  /** Bereits geladene Liste (AI-Act hält sie im Store am Objekt). */
  vorgeladen?: any[] | null
}>(), {
  objektTitel: '',
  repoVorschlag: '',
  textZiel: 'den Kommentar',
  mitUebernahme: true,
  darstellung: 'block',
  vorgeladen: null,
})

const emit = defineEmits<{
  /** Nach jeder Änderung — die Maske lädt ihre Daten nach. */
  geaendert: [ergebnis?: any]
  /** Nach einer Übernahme: der Freitext des Objekts hat sich geändert. */
  uebernommen: [ergebnis: any]
}>()

type Busy = '' | 'anlegen' | 'verknuepfen' | 'abgleichen' | 'uebernehmen' | 'entknuepfen'
const busy = ref<Busy>('')
const fehler = ref('')
const eigene = ref<any[]>([])
// Eindeutige Kennung für die `for`/`id`-Paare — mehrere Instanzen je Seite sind
// der Normalfall (eine je Tabellenzeile).
const lauf = Math.random().toString(36).slice(2, 8)

const issues = computed<any[]>(() =>
  Array.isArray(props.vorgeladen) ? props.vorgeladen : eigene.value)

const basis = computed(() =>
  `${props.apiBase}/projekte/${encodeURIComponent(props.projektName)}`
  + `/${props.objektPfad}/${encodeURIComponent(String(props.objektId ?? ''))}`)

/** `#123` (GitHub) bzw. `#45` (GitLab-iid) — beide Schlüsselräume (#1846). */
const nummer = (i: any) => {
  const n = i?.issue_number ?? i?.number ?? i?.issue_iid ?? i?.iid
  return n ? `#${n}` : ''
}

const meldung = (e: any, ersatz: string) =>
  e?.response?.data?.error || ersatz

const lade = async () => {
  if (props.vorgeladen !== null) return
  if (!props.objektId || !props.projektName) {
    eigene.value = []
    return
  }
  try {
    const res = await apiClient.get(`${basis.value}/issues`)
    eigene.value = Array.isArray(res.data) ? res.data : (res.data?.items || [])
  } catch {
    eigene.value = []
  }
}

watch(() => [props.objektId, props.projektName, props.objektPfad], () => lade(),
      { immediate: true })

// ── Anlegen ───────────────────────────────────────────────────────────────
const anlegen = ref({ open: false, provider: '', repo: '', titel: '',
                      body: '', fehler: '', erzeugt: null as any })

const oeffneAnlegen = () => {
  anlegen.value = { open: true, provider: '', repo: props.repoVorschlag || '',
                    titel: '', body: '', fehler: '', erzeugt: null }
}

const legeAn = async () => {
  busy.value = 'anlegen'
  anlegen.value.fehler = ''
  try {
    // Leere Felder werden **weggelassen**, nicht als leere Zeichenkette
    // geschickt: Der Server nimmt sonst den leeren Wert als Override und
    // findet kein Repository, obwohl eines im Projekt steht.
    const res = await apiClient.post(`${basis.value}/issues`, {
      provider: anlegen.value.provider || undefined,
      repo: anlegen.value.repo.trim() || undefined,
      title: anlegen.value.titel || undefined,
      body: anlegen.value.body || undefined,
    })
    // Antwortform ist eine Obermenge (#1846): `created` und `ok` stehen beide da.
    if (res.data?.created || res.data?.ok) {
      anlegen.value.erzeugt = res.data
      await lade()
      emit('geaendert', res.data)
    } else {
      anlegen.value.fehler = 'Das Issue wurde nicht angelegt.'
    }
  } catch (e: any) {
    anlegen.value.fehler = meldung(e, 'Issue konnte nicht angelegt werden.')
  } finally {
    busy.value = ''
  }
}

// ── Verknüpfen ────────────────────────────────────────────────────────────
const verknuepfen = ref({ open: false, url: '', titel: '', fehler: '' })

const oeffneVerknuepfen = () => {
  verknuepfen.value = { open: true, url: '', titel: '', fehler: '' }
}

const verknuepfe = async () => {
  if (!verknuepfen.value.url.trim()) return
  busy.value = 'verknuepfen'
  verknuepfen.value.fehler = ''
  try {
    const res = await apiClient.post(`${basis.value}/issues/link`, {
      url: verknuepfen.value.url.trim(),
      title: verknuepfen.value.titel || undefined,
    })
    if (res.data?.linked || res.data?.ok) {
      verknuepfen.value.open = false
      await lade()
      emit('geaendert', res.data)
    } else {
      verknuepfen.value.fehler = 'Die Verknüpfung wurde nicht angelegt.'
    }
  } catch (e: any) {
    verknuepfen.value.fehler = meldung(e, 'Verknüpfung fehlgeschlagen.')
  } finally {
    busy.value = ''
  }
}

// ── Abgleichen ────────────────────────────────────────────────────────────
const abgleichen = async () => {
  busy.value = 'abgleichen'
  fehler.value = ''
  try {
    const res = await apiClient.post(`${basis.value}/issues/sync`, {})
    await lade()
    // Der Abgleich kann „⚠️ Neubewertung erforderlich" in den Freitext
    // geschrieben haben (#1850) — die Maske muss nachladen, sonst steht die
    // Markierung in der Datenbank und nicht auf dem Schirm.
    emit('geaendert', res.data)
  } catch (e: any) {
    fehler.value = meldung(e, 'Abgleich fehlgeschlagen.')
  } finally {
    busy.value = ''
  }
}

// ── Übernehmen ────────────────────────────────────────────────────────────
const uebernahme = ref({ open: false, text: '', fehler: '' })

const oeffneUebernahme = () => {
  uebernahme.value = { open: true, text: '', fehler: '' }
}

const uebernimm = async (nutzlast: any) => {
  busy.value = 'uebernehmen'
  uebernahme.value.fehler = ''
  try {
    const res = await apiClient.post(`${basis.value}/import-issue`, nutzlast)
    uebernahme.value.open = false
    emit('uebernommen', res.data)
    emit('geaendert', res.data)
  } catch (e: any) {
    uebernahme.value.fehler = meldung(e, 'Übernahme fehlgeschlagen.')
  } finally {
    busy.value = ''
  }
}

const uebernimmAusVerknuepften = () => uebernimm({})
const uebernimmText = () => {
  if (!uebernahme.value.text.trim()) return
  return uebernimm({ issue_context: uebernahme.value.text })
}

// ── Entknüpfen ────────────────────────────────────────────────────────────
const entknuepfen = async (linkId: string) => {
  if (!confirm('Verknüpfung wirklich entfernen?')) return
  busy.value = 'entknuepfen'
  fehler.value = ''
  try {
    const res = await apiClient.delete(
      `${basis.value}/issues/${encodeURIComponent(String(linkId))}`)
    await lade()
    emit('geaendert', res.data)
  } catch (e: any) {
    fehler.value = meldung(e, 'Verknüpfung konnte nicht entfernt werden.')
  } finally {
    busy.value = ''
  }
}

// `issues` nach außen, damit die Maske die Liste für die Transparenz der
// Neubewertung zeigen kann (#1527), ohne sie ein zweites Mal zu holen.
defineExpose({ lade, issues })
</script>

<style scoped>
.iv-block {
  border: 1px solid var(--color-border); border-radius: 6px;
  padding: 10px 14px; margin-top: 12px; background: #f9f9f9;
}

.iv-block legend {
  padding: 0 6px; font-weight: 600; font-size: 12px;
  color: var(--color-primary); text-transform: uppercase;
}

.iv-leer { color: #888; font-size: 12px; font-style: italic; }
.iv-liste { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; }

.iv-eintrag {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 8px; background: white; border-radius: 3px; font-size: 12px;
}

.iv-status {
  padding: 2px 8px; border-radius: 3px;
  font-size: 10px; font-weight: 600; text-transform: uppercase;
}

.iv-status.open { background: #e3f2fd; color: #1565c0; }
.iv-status.closed { background: #e8f5e9; color: #2e7d32; }

.iv-link {
  flex: 1; color: #333; text-decoration: none;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.iv-link:hover { text-decoration: underline; color: var(--color-primary); }

.iv-knoepfe { display: flex; gap: 6px; flex-wrap: wrap; }

.iv-knopf {
  background: white; border: 1px solid #b3d4f5; color: #1565c0;
  padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;
}

.iv-knopf:hover:not(:disabled) { background: #1565c0; color: white; }
.iv-knopf:disabled { opacity: 0.5; cursor: not-allowed; }

/* Kompakte Form (Tabellenzelle) */
.iv-zeile { display: inline-flex; align-items: center; gap: 4px; flex-wrap: wrap; }

.iv-pille {
  padding: 1px 6px; border-radius: 3px; font-size: 11px;
  text-decoration: none; background: #e3f2fd; color: #1565c0;
}

.iv-pille.closed { background: #e8f5e9; color: #2e7d32; }

.iv-symbol {
  background: none; border: 1px solid #ddd;
  min-width: 22px; height: 22px; padding: 0 3px;
  border-radius: 3px; cursor: pointer; color: #666; font-size: 12px;
}

.iv-symbol:hover:not(:disabled) { background: #e3f2fd; border-color: #1565c0; }
.iv-symbol:disabled { opacity: 0.5; cursor: not-allowed; }
.iv-weg:hover:not(:disabled) { background: #ffebee; color: #c62828; border-color: #c62828; }

.iv-vorbehalt { margin: 0 0 10px; font-size: 12px; color: #e65100; }

.iv-feld { margin-bottom: 12px; }
.iv-feld label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.iv-feld small { display: block; font-size: 11px; color: #888; margin-top: 2px; }

.iv-feld input, .iv-feld select, .iv-feld textarea {
  width: 100%; padding: 8px 10px;
  border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px;
}

.iv-feld textarea { font-family: monospace; font-size: 12px; resize: vertical; }

:deep(.mr-inhalt) textarea {
  width: 100%; padding: 8px;
  border: 1px solid var(--color-border); border-radius: 4px;
  font-family: monospace; font-size: 12px; resize: vertical;
}

.iv-erfolg {
  background: #e8f5e9; padding: 10px 14px; border-radius: 4px;
  margin-top: 12px; font-size: 13px; border: 1px solid #81c784;
}

.iv-erfolg a { color: #2e7d32; }

.iv-primaer, .iv-sekundaer {
  padding: 8px 16px; border: none; border-radius: 4px;
  cursor: pointer; font-size: 13px;
}

.iv-primaer { background: var(--color-primary); color: white; }
.iv-primaer:disabled { opacity: 0.6; cursor: not-allowed; }
.iv-sekundaer { background: #e0e0e0; color: #333; }
</style>
