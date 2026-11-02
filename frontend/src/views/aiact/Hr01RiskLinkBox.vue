<template>
  <!-- #1561: AIA-HR-01 — Risikomanagement-System (Art. 9) über die verknüpfte Risikobewertung -->
  <section class="hr01-box">
    <h4>🔗 Risikomanagement-Nachweis (Art. 9)</h4>
    <p v-if="loading" class="muted">Lädt…</p>

    <template v-else-if="link.linked_risk_projekt">
      <p>
        Verknüpft mit <strong>{{ link.linked_risk_projekt }}</strong>
        <router-link :to="{ path: '/risikobewertung', query: { projekt: link.linked_risk_projekt } }" class="ext">→ öffnen</router-link>
      </p>
      <ul v-if="link.hr01" class="stats">
        <li>{{ link.hr01.stats.total }} Risiken · {{ link.hr01.stats.bewertet }} bewertet</li>
        <li>{{ link.hr01.stats.hoch }} hoch/kritisch · {{ link.hr01.stats.hoch_behandelt }} behandelt</li>
      </ul>
      <p v-if="link.hr01" class="vorschlag">
        Vorschlag: <strong>Score {{ link.hr01.score }}</strong> — {{ link.hr01.kommentar }}
      </p>
      <!-- #1571: Risiken direkt hier ermitteln — ohne Wechsel in die Risikobewertung -->
      <p v-if="link.hr01 && !link.hr01.stats.total" class="hint-empty">
        Die Risikobewertung enthält noch keine Risiken. Ermittle sie mit dem Risiken-Assistenten —
        er nutzt Zweck, Architektur und Risikoklasse dieses KI-Systems.
      </p>
      <div class="row">
        <button :class="link.hr01 && !link.hr01.stats.total ? 'btn-primary' : 'btn-secondary'" :disabled="busy"
                @click="assistentOpen = true">🪄 Risiken mit Assistent ermitteln</button>
        <button :class="link.hr01 && !link.hr01.stats.total ? 'btn-secondary' : 'btn-primary'" :disabled="busy"
                @click="apply">✅ Nachweis in Bewertung übernehmen</button>
      </div>
      <p class="muted small">
        Der Score folgt dem Inhalt der Risikobewertung (erfasst → bewertet → hohe/kritische behandelt)
        und wird auch von der Auto-/Massenbewertung so verwendet.
      </p>
    </template>

    <template v-else>
      <p class="muted">
        Art. 9 verlangt ein dokumentiertes Risikomanagement-System. Verknüpfe dafür eine
        Risikobewertung mit Bewertungsart <strong>EU-AI-Act</strong> — sie fließt dann in die Bewertung
        dieser Anforderung ein.
      </p>
      <div class="row">
        <select v-model="sel" :disabled="!candidates.length">
          <option value="">{{ candidates.length ? '— vorhandene Risikobewertung wählen —' : 'keine EU-AI-Act-Risikobewertung vorhanden' }}</option>
          <option v-for="c in candidates" :key="c.name" :value="c.name">
            {{ c.name }}{{ c.firma_match ? '' : ` (${c.unternehmen || 'ohne Firma'})` }}
          </option>
        </select>
        <button class="btn-secondary" :disabled="busy || !sel" @click="linkExisting">Verknüpfen</button>
      </div>
      <div class="row">
        <button class="btn-primary" :disabled="busy" @click="createNew">➕ Neue EU-AI-Act-Risikobewertung anlegen & verknüpfen</button>
      </div>
    </template>
    <p v-if="msg" class="msg">{{ msg }}</p>

    <RisikoAssistent
      :open="assistentOpen"
      :projekt-name="link.linked_risk_projekt || null"
      :prefill="assistentPrefill"
      @close="assistentOpen = false"
      @applied="onAssistentApplied"
    />
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import apiClient from '../../api/client'
import { useAiActStore } from '../../stores/aiact'
import RisikoAssistent from '../risikobewertung/RisikoAssistent.vue'

const emit = defineEmits<{ (e: 'saved'): void }>()
const store = useAiActStore()
const link = ref<any>({ linked_risk_projekt: null })
const candidates = ref<any[]>([])
const sel = ref('')
const loading = ref(true)
const busy = ref(false)
const msg = ref('')
const assistentOpen = ref(false)
const assistentPrefill = computed(() => {
  const p: any = store.selectedProjektObj || {}
  return {
    anwendung: p.produkt || p.name || '',
    beschreibung: p.beschreibung || '',
    aiact_projekt: store.selectedProjekt || '',
  }
})

async function onAssistentApplied(n: number) {
  await load()
  msg.value = `${n} Risiken angelegt. Bewerte sie in der Risikobewertung und übernimm dann den Nachweis.`
}

const url = (s: string) => `/aiact/projekte/${encodeURIComponent(store.selectedProjekt || '')}${s}`

async function load() {
  loading.value = true
  link.value = await store.fetchRiskLink()
  if (!link.value?.linked_risk_projekt) candidates.value = await store.fetchRiskLinkCandidates()
  loading.value = false
}

async function linkExisting() {
  busy.value = true
  const r = await store.setRiskLink(sel.value)
  busy.value = false
  msg.value = r ? 'Risikobewertung verknüpft.' : (store.error || 'Verknüpfen fehlgeschlagen.')
  if (r) await load()
}

async function createNew() {
  busy.value = true
  try {
    const r = await apiClient.post(url('/risk-link/create'))
    msg.value = `Risikobewertung „${r.data.linked_risk_projekt}" angelegt und verknüpft — Risiken dort erfassen.`
    await load()
  } catch (e: any) {
    msg.value = e?.response?.data?.error || 'Anlegen fehlgeschlagen.'
  } finally { busy.value = false }
}

async function apply() {
  busy.value = true
  try {
    const r = await apiClient.post(url('/anforderungen/AIA-HR-01/apply-risk-link'))
    msg.value = `Übernommen: Score ${r.data.score}.`
    emit('saved')
  } catch (e: any) {
    msg.value = e?.response?.data?.error || 'Übernahme fehlgeschlagen.'
  } finally { busy.value = false }
}

onMounted(load)
</script>

<style scoped>
.hr01-box {
  border: 1px solid #90caf9; background: #f3f8fe; border-radius: 6px;
  padding: 12px 14px; margin: 8px 0 12px;
}
.hr01-box h4 { margin: 0 0 6px; color: #1565c0; font-size: 14px; }
.row { display: flex; gap: 8px; align-items: center; margin: 6px 0; flex-wrap: wrap; }
.row select { flex: 1; min-width: 200px; padding: 6px; border: 1px solid var(--color-border); border-radius: 4px; }
.stats { margin: 4px 0; padding-left: 18px; font-size: 13px; }
.vorschlag { font-size: 13px; margin: 6px 0; }
.muted { color: #666; font-size: 13px; }
.small { font-size: 12px; }
.hint-empty { font-size: 13px; background: #fff8e1; border: 1px solid #ffe082; border-radius: 4px; padding: 6px 10px; margin: 6px 0; }
.msg { font-size: 13px; color: #1b5e20; margin: 6px 0 0; }
.ext { margin-left: 8px; font-size: 12px; }
.btn-primary, .btn-secondary { padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-primary { background: var(--color-primary); color: white; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: .6; cursor: not-allowed; }
</style>
