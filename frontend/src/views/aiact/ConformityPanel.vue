<template>
  <div class="conf-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein AI-Act-Projekt auswählen.</p>

    <template v-else-if="rec">
      <div class="conf-toolbar">
        <div class="toolbar-info">
          <strong>🏷️ Art. 43/48 — Konformitätsbewertung & CE-Kennzeichnung</strong>
          <span class="muted">Ergebnis: {{ rec.ergebnis }}</span>
        </div>
      </div>

      <!-- DoC-Gate-Status -->
      <div class="gate" :class="store.docGate?.doc_allowed ? 'gate-ok' : 'gate-blocked'" v-if="store.docGate">
        <strong v-if="store.docGate.doc_allowed">✅ DoC ausstellbar — Bewertungsweg abgeschlossen</strong>
        <strong v-else-if="store.docGate.reassessment_required">🔁 Re-Assessment nötig (wesentliche Änderung)</strong>
        <strong v-else>🔒 DoC gesperrt — Bewertungsweg nicht abgeschlossen</strong>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>

      <section class="card">
        <h4>Verfahrensweg</h4>
        <label class="full">
          <select v-model="rec.verfahren">
            <option v-for="v in store.verfahren" :key="v.code" :value="v.code">{{ v.label }}</option>
          </select>
        </label>
        <label class="inline">Ergebnis
          <select v-model="rec.ergebnis">
            <option v-for="e in ergebnisWerte" :key="e" :value="e">{{ e }}</option>
          </select>
        </label>
        <label class="inline">Bewertungsdatum<input type="date" v-model="rec.bewertungsdatum" /></label>
      </section>

      <!-- Annex VI: interne Kontrolle -->
      <section class="card" v-if="rec.verfahren === 'annex_vi_intern'">
        <h4>Annex-VI-Selbstprüfung (interne Kontrolle)</h4>
        <label class="check"><input type="checkbox" v-model="rec.qms_geprueft" /> QMS geprüft (Art. 17)</label>
        <label class="check"><input type="checkbox" v-model="rec.techdoc_geprueft" /> Technische Doku Annex IV geprüft (Art. 11)</label>
        <div class="checklist">
          <label class="check" v-for="c in store.checkliste" :key="c.key">
            <input type="checkbox" :checked="!!rec.checkliste[c.key]"
                   @change="rec.checkliste[c.key] = ($event.target as HTMLInputElement).checked" />
            {{ c.label }}
          </label>
        </div>
      </section>

      <!-- Annex VII: notifizierte Stelle -->
      <section class="card" v-else>
        <h4>Annex-VII-Pfad (notifizierte Stelle)</h4>
        <div class="grid">
          <label>NB-Name<input v-model="rec.notified_body_name" /></label>
          <label>NB-Kennnummer<input v-model="rec.notified_body_kennnummer" placeholder="4-stellig" /></label>
        </div>
        <div class="row">
          <input type="file" accept="application/pdf" @change="onCert" />
          <span class="muted" v-if="rec.nb_zertifikat_sha256">
            Zertifikat: ✓ (SHA-256 {{ rec.nb_zertifikat_sha256.slice(0, 12) }}…)
          </span>
        </div>
      </section>

      <!-- CE + Re-Assessment -->
      <section class="card">
        <h4>CE-Kennzeichnung & wesentliche Änderung</h4>
        <div class="grid">
          <label>CE angebracht am<input type="date" v-model="rec.ce_angebracht_am" /></label>
          <label>Wesentliche Änderung seit<input type="date" v-model="rec.wesentliche_aenderung_seit" /></label>
        </div>
        <p class="muted">Eine wesentliche Änderung nach dem Bewertungsdatum löst eine erneute Bewertung aus (Art. 43(4)).</p>
      </section>

      <div class="row">
        <button class="btn-primary" :disabled="busy" @click="save">💾 Speichern</button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import { useAiactConformityStore, type ConformityRecord } from '../../stores/aiactConformity'

const aiact = useAiActStore()
const store = useAiactConformityStore()

const projekt = computed(() => aiact.selectedProjekt)
const rec = ref<ConformityRecord | null>(null)
const busy = ref(false)
const message = ref('')

const ergebnisWerte = computed(() => store.ergebnisWerte.length ? store.ergebnisWerte
  : ['offen', 'konform', 'nicht_konform'])

async function load() {
  if (!projekt.value) return
  await store.loadConstants()
  await store.load(projekt.value)
  rec.value = store.record ? { ...store.record, checkliste: { ...(store.record.checkliste || {}) } } : null
}

async function save() {
  if (!projekt.value || !rec.value) return
  busy.value = true
  try {
    await store.save(projekt.value, rec.value)
    rec.value = store.record ? { ...store.record, checkliste: { ...(store.record.checkliste || {}) } } : rec.value
    message.value = 'Konformitätsbewertung gespeichert.'
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
  } finally { busy.value = false }
}

async function onCert(e: Event) {
  if (!projekt.value) return
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    await store.uploadCertificate(projekt.value, file)
    rec.value = store.record ? { ...store.record, checkliste: { ...(store.record.checkliste || {}) } } : rec.value
    message.value = 'Zertifikat hochgeladen.'
  } catch (err: any) {
    message.value = err?.response?.data?.error || 'Upload fehlgeschlagen.'
  }
}

watch(projekt, load, { immediate: true })
</script>

<style scoped>
.conf-panel { padding: 8px 0; }
.hint { color: #607d8b; padding: 16px; }
.conf-toolbar { background: #1565c0; color: #fff; padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; }
.toolbar-info strong { color: #fff; }
.toolbar-info .muted { color: #90caf9; margin-left: 12px; }
.gate { padding: 10px 14px; border-radius: 8px; margin-bottom: 12px; }
.gate-ok { background: #e8f5e9; border: 1px solid #a5d6a7; }
.gate-blocked { background: #fff3e0; border: 1px solid #ffcc80; }
.status-msg { color: #1565c0; margin: 8px 0; }
.card { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.card h4 { margin: 0 0 8px; color: #0d47a1; }
label { display: flex; flex-direction: column; font-size: 0.85em; color: #455a64; gap: 3px; }
label.full { width: 100%; }
label.inline { display: inline-flex; margin-right: 16px; margin-top: 8px; }
label.check { flex-direction: row; align-items: center; gap: 8px; margin: 6px 0; }
.grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.checklist { margin-top: 8px; border-top: 1px solid #eee; padding-top: 8px; }
input, select { box-sizing: border-box; padding: 4px 6px; }
select { width: 100%; }
.row { display: flex; gap: 12px; align-items: center; margin-top: 8px; }
.muted { color: #78909c; font-size: 0.85em; }
</style>
