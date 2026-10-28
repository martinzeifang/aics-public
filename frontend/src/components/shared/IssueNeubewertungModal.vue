<!--
  IssueNeubewertungModal (#1851) — „🧪 Neubewertung aus Issues".

  WAS DIESE ANSICHT IST UND WAS SIE NICHT IST
  Sie **zeigt**, was die verknüpften Issues über das Projekt sagen: je Objekt
  den aktuellen Wert, die Issues mit Status, und ob die Markierung
  „⚠️ Neubewertung erforderlich" bereits steht. Sie schreibt nichts, holt
  nichts von GitHub oder GitLab und bewertet nicht. Dafür gibt es die beiden
  anderen Knöpfe, und zwar genau einmal: „🔄 Issue-Status abgleichen" holt den
  Stand (beide Anbieter) und markiert; „📥 Issue-Feedback übernehmen" holt den
  Inhalt in den Freitext.

  Diesen Einstieg gab es nur in der Risikobewertung — dort als POST mit einem
  `refresh`-Schalter, der GitHub live abfragte und GitLab nur im Nebenzweig.
  Zwei Wege, denselben Stand von der Gegenstelle zu holen, sind zwei
  Wahrheiten über denselben Sachverhalt, und der eine davon kannte nur einen
  der beiden Anbieter.
-->
<template>
  <ModalRahmen :titel="`${A.neubewertung.text}: ${projektName}`" breite="breit"
               @close="$emit('close')">
    <template #inhalt>
      <FehlerHinweis :text="fehler" @close="fehler = ''" />
      <p v-if="laedt" class="in-hinweis">⏳ Lade verknüpfte Issues…</p>
      <template v-else>
        <p class="in-hinweis">
          {{ total }} Objekt(e) mit verknüpften Issues ·
          {{ markiert }} bereits als „⚠️ Neubewertung erforderlich" markiert ·
          {{ mitOffenen }} mit offenem Issue
        </p>
        <p class="in-stand">
          Gezeigt wird der <strong>gespeicherte</strong> Stand des letzten
          Abgleichs. „{{ A.statusAbgleichen.text }}" holt ihn frisch von
          GitHub bzw. GitLab und setzt die Markierungen.
        </p>
        <div v-if="eintraege.length" class="in-liste">
          <div v-for="e in eintraege" :key="`${e.object_kind}-${e.object_id}`"
               class="in-eintrag">
            <div class="in-kopf">
              <strong>{{ e.bezeichnung }} {{ e.object_id }}</strong>
              <span v-if="e.titel" class="in-titel">{{ e.titel }}</span>
              <span v-if="e.wert !== null && e.wert !== undefined" class="in-wert">
                {{ e.wert }}
              </span>
              <span v-if="e.markiert" class="in-markiert"
                    title="Die Markierung steht bereits im Freitext dieses Objekts">
                ⚠️ Neubewertung
              </span>
            </div>
            <ul class="in-issues">
              <li v-for="i in e.issues" :key="i.id">
                <span class="in-status" :class="i.offen ? 'open' : 'closed'">
                  {{ i.state || (i.offen ? 'open' : 'closed') }}
                </span>
                <a :href="safeUrl(i.url)" target="_blank" rel="noopener noreferrer">
                  {{ i.provider }}{{ nummer(i) }} – {{ i.title || '(ohne Titel)' }}
                </a>
                <span v-if="i.comments != null" class="in-kommentare">
                  💬 {{ i.comments }}
                </span>
              </li>
            </ul>
          </div>
        </div>
        <p v-else class="in-leer">
          In diesem Projekt ist noch kein Issue verknüpft. „{{ A.issuesAnlegen.text }}"
          legt für die offenen Punkte Issues an.
        </p>
      </template>
    </template>
    <template #fuss>
      <button class="in-sekundaer" type="button" :disabled="laedt" @click="lade">
        🔄 Aktualisieren
      </button>
      <button class="in-primaer" type="button" @click="$emit('close')">Schließen</button>
    </template>
  </ModalRahmen>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import apiClient from '../../api/client'
import { safeUrl } from '../../utils/safeUrl'
import { PROJEKT_AKTIONEN as A } from '../../utils/aktionen'
import FehlerHinweis from './FehlerHinweis.vue'
import ModalRahmen from './ModalRahmen.vue'

const props = defineProps<{
  apiBase: string
  projektName: string
}>()

defineEmits<{ close: [] }>()

const laedt = ref(true)
const fehler = ref('')
const eintraege = ref<any[]>([])
const total = ref(0)
const markiert = ref(0)
const mitOffenen = ref(0)

const nummer = (i: any) => {
  const n = i?.issue_number ?? i?.issue_iid
  return n ? ` #${n}` : ''
}

const lade = async () => {
  laedt.value = true
  fehler.value = ''
  try {
    const res = await apiClient.get(
      `${props.apiBase}/projekte/${encodeURIComponent(props.projektName)}/issues/neubewertung`)
    eintraege.value = res.data?.items || []
    total.value = Number(res.data?.total || 0)
    markiert.value = Number(res.data?.markiert || 0)
    mitOffenen.value = Number(res.data?.mit_offenen_issues || 0)
  } catch (e: any) {
    fehler.value = e?.response?.data?.error
      || 'Die verknüpften Issues konnten nicht geladen werden.'
  } finally {
    laedt.value = false
  }
}

onMounted(lade)
</script>

<style scoped>
.in-hinweis { color: #607d8b; font-size: 13px; margin: 0 0 6px; }

.in-stand {
  background: #f5faff; border: 1px solid #cfe3f7; color: #37474f;
  padding: 8px 12px; border-radius: 6px; font-size: 12px; margin: 0 0 12px;
}

.in-liste { display: flex; flex-direction: column; gap: 8px; }

.in-eintrag {
  border: 1px solid var(--color-border); border-radius: 6px;
  padding: 8px 10px; background: #fafafa;
}

.in-kopf { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px; }
.in-titel { color: #546e7a; font-size: 12px; }

.in-wert {
  padding: 1px 8px; border-radius: 10px; background: #eceff1;
  color: #37474f; font-size: 11px; font-weight: 600;
}

.in-markiert {
  padding: 1px 8px; border-radius: 10px;
  background: #fff3e0; color: #b26a00; font-size: 11px; font-weight: 600;
}

.in-issues { margin: 6px 0 0; padding-left: 4px; list-style: none; }

.in-issues li {
  display: flex; align-items: center; gap: 6px;
  padding: 2px 0; font-size: 12px;
}

.in-issues a { color: #333; text-decoration: none; }
.in-issues a:hover { text-decoration: underline; color: var(--color-primary); }

.in-status {
  padding: 1px 6px; border-radius: 3px;
  font-size: 10px; font-weight: 600; text-transform: uppercase;
}

.in-status.open { background: #e3f2fd; color: #1565c0; }
.in-status.closed { background: #e8f5e9; color: #2e7d32; }
.in-kommentare { color: #78909c; font-size: 11px; }
.in-leer { color: #888; font-style: italic; font-size: 13px; }

.in-primaer, .in-sekundaer {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
}

.in-primaer { background: var(--color-primary); color: white; }
.in-sekundaer { background: #e0e0e0; color: #333; }
.in-sekundaer:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
