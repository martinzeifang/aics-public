<template>
  <div class="modal-overlay" @click.self="onCancel">
    <div class="modal-content">
      <div class="modal-header">
        <h3>
          <code class="req-id">{{ requirement.id }}</code>
          {{ requirement.titel || requirement.title }}
        </h3>
        <button class="btn-close" @click="onCancel">✕</button>
      </div>

      <div class="modal-body">
        <div class="meta-row">
          <span class="meta-badge">{{ requirement.kapitel }}</span>
          <span v-if="requirement.ref" class="meta-ref">{{ requirement.ref }}</span>
          <span v-if="requirement.gewichtung" class="meta-weight">
            Gewichtung: {{ requirement.gewichtung }}
          </span>
          <span v-if="requirement.quelle === 'custom'" class="meta-custom">Custom</span>
          <span v-if="requirement.quelle === 'override'" class="meta-override">Override</span>
        </div>

        <div v-if="requirement.beschreibung" class="info-section">
          <h4>Beschreibung</h4>
          <p>{{ requirement.beschreibung }}</p>
        </div>

        <div v-if="requirement.hinweise" class="info-section">
          <h4>Hinweise zur Umsetzung</h4>
          <p>{{ requirement.hinweise }}</p>
        </div>

        <fieldset>
          <legend>Bewertung</legend>

          <div class="form-row">
            <label>Reifegrad (0-5)</label>
            <div class="score-row">
              <input v-model.number="form.bewertung" type="range" min="0" max="5" step="1" />
              <span class="score-display" :style="{ background: scoreColor }">
                {{ form.bewertung }} – {{ scoreLabel }}
              </span>
            </div>
          </div>

          <div class="form-row">
            <label>Kommentar / IST-Zustand</label>
            <textarea v-model="form.kommentar" rows="3"
                      placeholder="Wie ist die aktuelle Umsetzung?"></textarea>
          </div>

          <div class="form-row">
            <label>Maßnahme zur Verbesserung</label>
            <textarea v-model="form.massnahme" rows="2"
                      placeholder="Was wurde/wird getan, um den Reifegrad zu verbessern?"></textarea>
          </div>

          <div class="form-grid">
            <div class="form-row">
              <label>Verantwortlich</label>
              <input v-model="form.verantwortlich" placeholder="Name oder Rolle" />
            </div>
            <div class="form-row">
              <label>Zieldatum</label>
              <input v-model="form.zieldatum" type="date" />
            </div>
          </div>
        </fieldset>

        <!-- Optionaler Slot für KI-Aktionen + Issue-Verknüpfungen (vom Parent gefüllt) -->
        <slot name="actions" />

        <div v-if="error" class="alert alert-error">{{ error }}</div>
      </div>

      <div class="modal-footer">
        <button class="btn-secondary" @click="onCancel">Abbrechen</button>
        <button class="btn-primary" @click="onSave" :disabled="saving">
          {{ saving ? 'Speichert…' : 'Speichern' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

const props = defineProps<{
  requirement: any
}>()

const emit = defineEmits<{
  save: [data: { bewertung: number; kommentar: string; massnahme: string; verantwortlich: string; zieldatum: string }]
  cancel: []
}>()

const form = ref({
  bewertung: 0,
  kommentar: '',
  massnahme: '',
  verantwortlich: '',
  zieldatum: '',
})

const error = ref('')
const saving = ref(false)

watch(() => props.requirement, (r) => {
  if (!r) return
  form.value = {
    bewertung: Number(r.bewertung ?? r.score ?? 0),
    kommentar: r.kommentar || r.notes || '',
    massnahme: r.massnahme || '',
    verantwortlich: r.verantwortlich || '',
    zieldatum: r.zieldatum || '',
  }
  error.value = ''
}, { immediate: true })

const SCORE_LABELS = ['Nicht bewertet', 'Nicht erfüllt', 'In Planung', 'Teilweise', 'Weitgehend', 'Vollständig']
const SCORE_COLORS = ['#9e9e9e', '#c62828', '#e65100', '#f57f17', '#558b2f', '#2e7d32']

const scoreLabel = computed(() => SCORE_LABELS[form.value.bewertung] || '')
const scoreColor = computed(() => SCORE_COLORS[form.value.bewertung] || '#9e9e9e')

const onSave = async () => {
  saving.value = true
  emit('save', { ...form.value })
  saving.value = false
}

const onCancel = () => emit('cancel')
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1100;
}

.modal-content {
  background: white;
  border-radius: 8px;
  max-width: 720px;
  width: 95%;
  max-height: 90vh;
  display: flex; flex-direction: column;
}

.modal-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
  gap: 8px;
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
  color: var(--color-text-primary);
  display: flex; align-items: center; gap: 8px;
  flex-wrap: wrap;
}

.req-id {
  background: #e3f2fd;
  color: var(--color-primary);
  padding: 3px 8px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: 600;
}

.btn-close { background: none; border: none; font-size: 22px; color: #999; cursor: pointer; }

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--color-border);
}

.meta-row {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.meta-badge, .meta-ref, .meta-weight, .meta-custom, .meta-override {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 3px;
}

.meta-badge { background: #1565c0; color: white; }
.meta-ref { background: #f5f5f5; color: #555; font-family: monospace; }
.meta-weight { background: #fff8e1; color: #e65100; }
.meta-custom { background: #e8f5e9; color: #2e7d32; }
.meta-override { background: #fce4ec; color: #c2185b; }

.info-section {
  background: #f9f9f9;
  border-radius: 4px;
  padding: 10px 14px;
  margin-bottom: 12px;
}

.info-section h4 {
  margin: 0 0 4px;
  font-size: 12px;
  color: var(--color-primary);
  text-transform: uppercase;
}

.info-section p {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: #333;
  white-space: pre-wrap;
}

fieldset {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 14px 16px;
  margin-bottom: 12px;
}

fieldset legend {
  padding: 0 6px;
  font-weight: 600;
  font-size: 12px;
  color: var(--color-primary);
  text-transform: uppercase;
}

.form-row { margin-bottom: 12px; }
.form-row label {
  display: block;
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 4px;
}

.form-row input,
.form-row textarea,
.form-row select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.score-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.score-row input[type="range"] {
  flex: 1;
  padding: 0;
}

.score-display {
  padding: 5px 12px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
  color: white;
  white-space: nowrap;
  min-width: 180px;
  text-align: center;
}

.alert-error {
  background: #ffebee;
  color: #c62828;
  padding: 10px;
  border-radius: 4px;
  margin-top: 12px;
  border: 1px solid #ef5350;
}

.btn-primary, .btn-secondary {
  padding: 8px 18px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.btn-primary { background: var(--color-primary); color: white; }
.btn-primary:disabled { opacity: 0.6; }
.btn-secondary { background: #e0e0e0; color: #333; }
</style>
