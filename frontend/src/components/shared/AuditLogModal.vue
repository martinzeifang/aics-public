<!--
  AuditLogModal (#1851) — der Revisionspfad eines Projekts, in allen sechs
  Modulen dieselbe Ansicht.

  Alle sechs Module schreiben seit #1338 in dieselbe append-only Spur;
  **ansehen** konnte man das nur in der Risikobewertung und in der
  Administration. Der Anwender, der belegen muss, wer eine Bewertung geändert
  hat, kommt an die Administration nicht heran — und genau er wird gefragt.

  Zwei Quellen, je Zeile ausgewiesen: der **Revisionspfad** (wer hat welche
  Handlung ausgelöst) und, wo es eines gibt, das **Änderungsprotokoll** auf
  Feldebene. Zusammengeführt hat sie der Server (`shared/audit_api`); diese
  Komponente ist dumm und zeigt nur.
-->
<template>
  <ModalRahmen :titel="`${A.auditLog.text}: ${projektName}`" breite="breit"
               @close="$emit('close')">
    <template #inhalt>
      <FehlerHinweis :text="fehler" @close="fehler = ''" />
      <p v-if="laedt" class="al-hinweis">⏳ Lade Revisionspfad…</p>
      <template v-else>
        <p class="al-hinweis">
          {{ total }} Eintrag/Einträge
          <template v-if="quellen.length">
            · Quellen: {{ quellen.map(q => QUELLEN[q] || q).join(' + ') }}
          </template>
        </p>
        <!-- Die Grenze gehört in die Ansicht. Eine Liste, die ihren Rand
             verschweigt, behauptet Vollständigkeit (#1824). -->
        <p v-if="fensterErschoepft" class="al-grenze">
          ⚠️ Es wurden nur die jüngsten Einträge dieses Moduls durchgesehen —
          ältere sind in dieser Ansicht <strong>nicht geprüft</strong>.
          Der vollständige Revisionspfad steht der Administration offen.
        </p>
        <table v-if="eintraege.length" class="al-tabelle">
          <thead>
            <tr>
              <th>Zeitpunkt</th>
              <th>Handlung</th>
              <th>Wer</th>
              <th>Objekt</th>
              <th>Quelle</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(e, i) in eintraege" :key="i">
              <td class="al-zeit">{{ zeitpunkt(e.zeit) }}</td>
              <td><code>{{ e.aktion }}</code>
                <span v-if="e.ergebnis && e.ergebnis !== 'success'"
                      class="al-ergebnis">{{ e.ergebnis }}</span>
              </td>
              <td class="al-wer">{{ e.akteur || '—' }}</td>
              <td>
                <template v-if="e.objekt || e.objekt_id">
                  {{ e.objekt }}<template v-if="e.objekt_id"> {{ e.objekt_id }}</template>
                </template>
                <template v-else>—</template>
              </td>
              <td><span class="al-quelle" :class="e.quelle">{{ QUELLEN[e.quelle] || e.quelle }}</span></td>
            </tr>
          </tbody>
        </table>
        <p v-else class="al-leer">
          Für dieses Projekt ist noch kein Eintrag im Revisionspfad.
        </p>
      </template>
    </template>
    <template #fuss>
      <button class="al-sekundaer" type="button" :disabled="laedt" @click="lade">
        🔄 Aktualisieren
      </button>
      <button class="al-primaer" type="button" @click="$emit('close')">Schließen</button>
    </template>
  </ModalRahmen>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import apiClient from '../../api/client'
import { PROJEKT_AKTIONEN as A } from '../../utils/aktionen'
import FehlerHinweis from './FehlerHinweis.vue'
import ModalRahmen from './ModalRahmen.vue'

const props = defineProps<{
  /** Modul-Prefix: `/cra`, `/nis2`, `/aiact`, `/dsgvo`, `/wiba`, `/risikobewertung`. */
  apiBase: string
  projektName: string
}>()

defineEmits<{ close: [] }>()

/** Gleiche Benennung wie `shared.audit_api.QUELLEN`. */
const QUELLEN: Record<string, string> = {
  revisionspfad: 'Revisionspfad',
  aenderungen: 'Änderungsprotokoll',
}

const laedt = ref(true)
const fehler = ref('')
const eintraege = ref<any[]>([])
const total = ref(0)
const quellen = ref<string[]>([])
const fensterErschoepft = ref(false)

const zeitpunkt = (wert: unknown) => {
  const text = String(wert ?? '')
  if (!text) return '—'
  const d = new Date(text)
  return Number.isNaN(d.getTime()) ? text : d.toLocaleString('de-DE')
}

const lade = async () => {
  laedt.value = true
  fehler.value = ''
  try {
    const res = await apiClient.get(
      `${props.apiBase}/projekte/${encodeURIComponent(props.projektName)}/audit`,
      { params: { limit: 500 } })
    eintraege.value = res.data?.eintraege || []
    total.value = Number(res.data?.total || 0)
    quellen.value = res.data?.quellen || []
    fensterErschoepft.value = !!res.data?.fenster_erschoepft
  } catch (e: any) {
    fehler.value = e?.response?.data?.error
      || 'Der Revisionspfad konnte nicht geladen werden.'
  } finally {
    laedt.value = false
  }
}

onMounted(lade)
</script>

<style scoped>
.al-hinweis { color: #607d8b; font-size: 13px; margin: 0 0 10px; }

.al-grenze {
  background: #fff8e1; border: 1px solid #ffe082; color: #795548;
  padding: 8px 12px; border-radius: 6px; font-size: 12px; margin: 0 0 12px;
}

.al-tabelle { width: 100%; border-collapse: collapse; font-size: 12px; }

.al-tabelle th {
  text-align: left; padding: 6px 8px; background: #f5f5f5;
  border-bottom: 2px solid var(--color-border); font-weight: 600;
  position: sticky; top: 0;
}

.al-tabelle td { padding: 5px 8px; border-bottom: 1px solid #eee; vertical-align: top; }
.al-tabelle code { font-size: 11px; color: #1565c0; }
.al-zeit { white-space: nowrap; color: #546e7a; }
.al-wer { max-width: 220px; overflow-wrap: anywhere; }

.al-ergebnis {
  margin-left: 6px; padding: 1px 6px; border-radius: 8px;
  background: #ffebee; color: #c62828; font-size: 10px; font-weight: 600;
}

.al-quelle {
  padding: 1px 6px; border-radius: 8px; font-size: 10px;
  font-weight: 600; white-space: nowrap;
}

.al-quelle.revisionspfad { background: #e3f2fd; color: #1565c0; }
.al-quelle.aenderungen { background: #f1f8e9; color: #558b2f; }

.al-leer { color: #888; font-style: italic; font-size: 13px; }

.al-primaer, .al-sekundaer {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
}

.al-primaer { background: var(--color-primary); color: white; }
.al-sekundaer { background: #e0e0e0; color: #333; }
.al-sekundaer:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
