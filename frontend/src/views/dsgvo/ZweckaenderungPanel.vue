<template>
  <div class="za-panel">
    <div class="intro-banner">
      <strong>{{ $t('dsgvo.zweckaenderungPanel.zweckanderungArt') }}</strong>
      <p class="hint">{{ $t('dsgvo.zweckaenderungPanel.dokumentierterKompatibilitatstestBei') }}</p>
    </div>

    <div v-if="!projektName" class="hint">{{ $t('common.projektWaehlen') }}</div>
    <template v-else>
      <button class="btn-primary" @click="openNew">{{ $t('dsgvo.zweckaenderungPanel.neueZweckanderung') }}</button>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>

      <table v-if="store.items.length" class="grid">
        <thead>
          <tr><th>ID</th><th>{{ $t('dsgvo.zweckaenderungPanel.ursprunglich') }}</th><th>{{ $t('dsgvo.zweckaenderungPanel.neuerZweck') }}</th><th>{{ $t('dsgvo.zweckaenderungPanel.vVT') }}</th><th>{{ $t('common.ergebnis') }}</th><th>{{ $t('common.actions') }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="z in store.items" :key="z.id">
            <td>{{ z.za_id }}</td>
            <td>{{ z.urspruenglicher_zweck }}</td>
            <td>{{ z.neuer_zweck }}</td>
            <td>{{ z.vvt_ref }}</td>
            <td><span class="pill" :class="'pill-' + z.ergebnis">{{ ergebnisLabel(z.ergebnis) }}</span></td>
            <td class="actions">
              <button class="btn-secondary" @click="openEdit(z)">✏️</button>
              <button class="btn-secondary" @click="store.exportZa(projektName!, z.id, 'docx')">📝</button>
              <button class="btn-secondary" @click="store.exportZa(projektName!, z.id, 'pdf')">📄</button>
              <button class="btn-danger-mini" @click="del(z)">🗑️</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="hint">{{ $t('dsgvo.zweckaenderungPanel.keineZweckanderungenErfasst') }}</p>
    </template>

    <!-- Editor -->
    <div v-if="editing" class="modal-backdrop" @click.self="editing = null">
      <div class="modal">
        <h3>{{ editing.id ? $t('dsgvo.zweckaenderungPanel.zweckanderungBearbeiten') : $t('dsgvo.zweckaenderungPanel.neueZweckanderung2') }}</h3>
        <label>ID <input v-model="editing.za_id" placeholder="ZA-001" /></label>
        <label>{{ $t('common.vVTReferenz') }} <input v-model="editing.vvt_ref" /></label>
        <label>{{ $t('dsgvo.zweckaenderungPanel.ursprunglicherZweck') }} <textarea v-model="editing.urspruenglicher_zweck" rows="2"></textarea></label>
        <label>{{ $t('dsgvo.zweckaenderungPanel.neuerZweck') }} <textarea v-model="editing.neuer_zweck" rows="2"></textarea></label>

        <div class="wizard">
          <button class="btn-secondary" @click="genPrompt">{{ $t('dsgvo.zweckaenderungPanel.kIPromptErzeugen') }}</button>
          <PromptAustausch v-if="prompt" v-model="aiResponse" :prompt="prompt"
                           prompt-titel="Prompt" antwort-titel="KI-Antwort"
                           :nummeriert="false" :prompt-zeilen="3" :antwort-zeilen="3"
                           :platzhalter="$t('dsgvo.zweckaenderungPanel.kIAntwortHierEinfugen')">
            <template #fuss>
              <button class="btn-secondary" @click="applyAi">{{ $t('dsgvo.zweckaenderungPanel.antwortUbernehmen') }}</button>
            </template>
          </PromptAustausch>
        </div>

        <fieldset>
          <legend>{{ $t('dsgvo.zweckaenderungPanel.artKriterien') }}</legend>
          <label>{{ $t('dsgvo.zweckaenderungPanel.aZusammenhangDerZwecke') }} <textarea v-model="editing.krit_zusammenhang" rows="2"></textarea></label>
          <label>{{ $t('dsgvo.zweckaenderungPanel.bErhebungskontext') }} <textarea v-model="editing.krit_kontext" rows="2"></textarea></label>
          <label>{{ $t('dsgvo.zweckaenderungPanel.cArtDerDatenArt') }} <textarea v-model="editing.krit_datenart" rows="2"></textarea></label>
          <label>{{ $t('dsgvo.zweckaenderungPanel.dMoglicheFolgen') }} <textarea v-model="editing.krit_folgen" rows="2"></textarea></label>
          <label>{{ $t('dsgvo.zweckaenderungPanel.eGeeigneteGarantien') }} <textarea v-model="editing.krit_garantien" rows="2"></textarea></label>
        </fieldset>

        <label>{{ $t('common.ergebnis') }}
          <select v-model="editing.ergebnis">
            <option value="offen">{{ $t('cra.pflichtDokuPanel.offen') }}</option>
            <option value="vereinbar">vereinbar</option>
            <option value="unvereinbar">{{ $t('dsgvo.zweckaenderungPanel.unvereinbarNeueRechtsgrundlageNotig') }}</option>
          </select>
        </label>
        <label>{{ $t('common.begruendung') }} <textarea v-model="editing.ergebnis_begruendung" rows="2"></textarea></label>
        <label v-if="editing.ergebnis === 'unvereinbar'">{{ $t('dsgvo.zweckaenderungPanel.neueRechtsgrundlage') }}
          <input v-model="editing.neue_rechtsgrundlage" /></label>
        <label>{{ $t('common.reviewer') }} <input v-model="editing.reviewer" /></label>
        <label>{{ $t('common.reviewDatum') }} <input v-model="editing.review_datum" type="date" /></label>

        <div class="modal-actions">
          <button class="btn-primary" @click="save">{{ $t('common.saveIcon') }}</button>
          <button class="btn-secondary" @click="editing = null">{{ $t('common.cancel') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import PromptAustausch from '../../components/shared/PromptAustausch.vue'
import { useDsgvoZweckaenderungStore, type Zweckaenderung } from '../../stores/dsgvoZweckaenderung'

const props = defineProps<{ projektName: string | null }>()
const store = useDsgvoZweckaenderungStore()

const editing = ref<Partial<Zweckaenderung> | null>(null)
const prompt = ref('')
const aiResponse = ref('')

const ergebnisLabel = (e: string) =>
  ({ vereinbar: 'vereinbar', unvereinbar: 'unvereinbar', offen: 'offen' } as any)[e] || e

const load = () => { if (props.projektName) store.fetchAll(props.projektName) }

const openNew = () => {
  prompt.value = ''; aiResponse.value = ''
  editing.value = {
    za_id: '', vvt_ref: '', urspruenglicher_zweck: '', neuer_zweck: '',
    krit_zusammenhang: '', krit_kontext: '', krit_datenart: '', krit_folgen: '',
    krit_garantien: '', ergebnis: 'offen', ergebnis_begruendung: '',
    neue_rechtsgrundlage: '', reviewer: '', review_datum: '',
  }
}

const openEdit = (z: Zweckaenderung) => {
  prompt.value = ''; aiResponse.value = ''
  editing.value = { ...z }
}

const genPrompt = async () => {
  if (!props.projektName || !editing.value) return
  prompt.value = await store.wizardPrompt(
    props.projektName, editing.value.urspruenglicher_zweck || '', editing.value.neuer_zweck || '')
}

const applyAi = async () => {
  if (!props.projektName || !editing.value) return
  const parsed = await store.wizardParse(props.projektName, aiResponse.value)
  if (parsed) editing.value = { ...editing.value, ...parsed }
}

const save = async () => {
  if (!props.projektName || !editing.value) return
  if (await store.save(props.projektName, editing.value)) editing.value = null
}

const del = async (z: Zweckaenderung) => {
  if (!props.projektName) return
  if (confirm(`Zweckänderung ${z.za_id} löschen?`)) await store.remove(props.projektName, z.id)
}

onMounted(load)
watch(() => props.projektName, load)
</script>

<style scoped>
.za-panel { display: flex; flex-direction: column; gap: 14px; padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 8px; }
.intro-banner .hint { color: #1565c0; font-size: 13px; margin: 4px 0 0; }
.hint { color: #666; font-size: 13px; }
.grid { width: 100%; border-collapse: collapse; font-size: 13px; }
.grid th, .grid td { border: 1px solid var(--color-border, #ddd); padding: 6px 8px; text-align: left; }
.grid th { background: #1565c0; color: white; }
.actions { display: flex; gap: 4px; flex-wrap: wrap; }
.pill { padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.pill-vereinbar { background: #e8f5e9; color: #2e7d32; }
.pill-unvereinbar { background: #ffebee; color: #c62828; }
.pill-offen { background: #eceff1; color: #607d8b; }
.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 14px; border-radius: 4px; cursor: pointer; align-self: flex-start; }
.btn-secondary { background: #e0e0e0; color: #333; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-danger-mini { background: #ffcdd2; color: #b71c1c; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.msg { font-size: 13px; }
.msg.err { color: #c62828; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: white; border-radius: 8px; padding: 20px 24px; width: min(640px, 94vw); max-height: 90vh; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.modal h3 { color: #1565c0; margin: 0 0 8px; }
.modal label { display: flex; flex-direction: column; font-size: 13px; gap: 2px; }
.modal input, .modal select, .modal textarea { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
.wizard { display: flex; flex-direction: column; gap: 6px; background: #f5f9ff; padding: 8px; border-radius: 6px; }
.prompt { background: #eef3fa; }
fieldset { border: 1px solid #ddd; border-radius: 6px; padding: 8px 10px; display: flex; flex-direction: column; gap: 8px; }
legend { color: #90caf9; font-weight: 600; font-size: 13px; }
.modal-actions { display: flex; gap: 8px; margin-top: 12px; }
</style>
