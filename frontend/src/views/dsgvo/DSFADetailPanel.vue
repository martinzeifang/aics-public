<template>
  <div class="dsfa-detail">
    <div class="dsfa-head">
      <h3>DSFA „{{ dpia?.titel || dpia?.dpia_id }}" — Art. 35 DSGVO</h3>
      <button class="btn-link" @click="$emit('close')">✕ Schließen</button>
    </div>

    <!-- Art. 35 Abs. 7 a + b — LOKAL im dsgvo_dpia-Hull -->
    <section class="block">
      <h4>Lokale Angaben (Art. 35 Abs. 7 lit. a + b)</h4>
      <div class="help-box">
        Diese Felder bleiben im DSGVO-Modul. Risiken (lit. c) und Maßnahmen (lit. d)
        werden in der verknüpften Risikobewertung geführt (read-only unten).
      </div>
      <dl class="kv">
        <dt>a) Beschreibung der Verarbeitung</dt>
        <dd>{{ link?.beschreibung_verarbeitung || '—' }}</dd>
        <dt>b) Notwendigkeit / Verhältnismäßigkeit</dt>
        <dd>{{ link?.notwendigkeit_grund || '—' }}</dd>
        <dt>Konsultation Aufsichtsbehörde (Art. 36)</dt>
        <dd>{{ Number(dpia?.konsultation_aufsicht) ? 'Ja' : 'Nein' }}</dd>
        <dt>Nächstes Review (Art. 35 Abs. 11)</dt>
        <dd>{{ dpia?.naechstes_review || '—' }}</dd>
      </dl>
    </section>

    <!-- Art. 35 Abs. 7 c + d — READ-ONLY aus verknüpftem rb_projekt -->
    <section class="block">
      <div class="rb-head">
        <h4>Risiken &amp; Maßnahmen (Art. 35 Abs. 7 lit. c + d)</h4>
        <a
          v-if="link?.rb_projekt_id"
          class="btn-primary jump"
          :href="`#/risikobewertung?projekt=${encodeURIComponent(link.rb_projekt_id)}`"
          :title="`Verknüpfte Risikobewertung „${link.rb_projekt_id}“ öffnen`"
        >↗ In Risikobewertung öffnen</a>
      </div>
      <div class="help-box">
        Read-only. Bearbeitung erfolgt in der verknüpften Risikobewertung
        <code v-if="link?.rb_projekt_id">{{ link.rb_projekt_id }}</code>
        (Framework {{ link?.framework || 'DSGVO-DSFA' }}).
      </div>

      <p v-if="loading" class="muted">Lade Risiken …</p>
      <p v-else-if="!link?.rb_projekt_id" class="muted">
        Keine verknüpfte Risikobewertung gefunden.
      </p>
      <p v-else-if="!link.risiken?.length" class="muted">
        Noch keine Risiken erfasst. Über „In Risikobewertung öffnen" anlegen.
      </p>
      <table v-else>
        <thead>
          <tr>
            <th>Nr.</th>
            <th>c) Bedrohung für Rechte/Freiheiten</th>
            <th>Wahrsch.</th>
            <th>Schwere</th>
            <th>d) Abhilfemaßnahme</th>
            <th>Risiko</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in link.risiken" :key="r.id" :class="{ resolved: r.is_resolved }">
            <td>{{ r.nr }}</td>
            <td>{{ r.bedrohung_rechte_freiheiten || r.risk_name || '—' }}</td>
            <td>{{ r.eintrittswahrscheinlichkeit || '—' }}</td>
            <td>{{ r.schwere || '—' }}</td>
            <td>{{ r.massnahme || '—' }}</td>
            <td><span class="risk-pill">{{ r.risiko_label || '—' }}</span></td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useDsgvoStore } from '../../stores/dsgvo'

const props = defineProps<{ dpia: any }>()
defineEmits<{ (e: 'close'): void }>()

const store = useDsgvoStore()
const link = ref<any | null>(null)
const loading = ref(false)

const load = async () => {
  if (!props.dpia?.id) return
  loading.value = true
  link.value = await store.fetchDsfaRiskLink(props.dpia.id)
  loading.value = false
}

watch(() => props.dpia?.id, load)
onMounted(load)
</script>

<style scoped>
.dsfa-detail { border: 1px solid #cfd8dc; border-radius: 8px; padding: 16px; margin-top: 12px; background: #fafafa; }
.dsfa-head { display: flex; justify-content: space-between; align-items: center; }
.dsfa-head h3 { margin: 0; font-size: 1.05rem; color: #1565c0; }
.block { margin-top: 16px; }
.block h4 { margin: 0 0 8px; color: #37474f; }
.rb-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.help-box { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 8px 12px; border-radius: 4px; margin: 8px 0; font-size: 0.88rem; }
.kv { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; }
.kv dt { font-weight: 600; color: #455a64; }
.kv dd { margin: 0; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 0.88rem; }
th, td { border: 1px solid #e0e0e0; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #eceff1; }
tr.resolved { opacity: 0.55; text-decoration: line-through; }
.risk-pill { display: inline-block; padding: 2px 8px; border-radius: 10px; background: #b71c1c; color: #fff; font-size: 0.78rem; }
.muted { color: #78909c; font-style: italic; }
.btn-primary { background: #1565c0; color: #fff; border: none; border-radius: 4px; padding: 6px 12px; cursor: pointer; text-decoration: none; font-size: 0.85rem; }
.btn-primary.jump:hover { background: #0d47a1; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; }
code { background: #eceff1; padding: 1px 4px; border-radius: 3px; }
</style>
