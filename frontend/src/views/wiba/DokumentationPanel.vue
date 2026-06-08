<template>
  <div class="wiba-doku">
    <!-- Intro / Hier starten -->
    <div class="intro-banner">
      <h3>🚀 Hier starten — WiBA „Weg in die Basis-Absicherung"</h3>
      <p>
        WiBA ist der vom BSI empfohlene Einstieg in den IT-Grundschutz für kleine
        und mittlere Organisationen. Anhand kurzer <strong>Prüffragen</strong> zu
        den wichtigsten Themen prüfen Sie, ob grundlegende Sicherheits­maßnahmen
        umgesetzt sind. Jede Frage beantworten Sie mit <strong>Ja</strong>,
        <strong>Nein</strong> oder <strong>Nicht relevant</strong> — daraus
        ergibt sich Ihr Reifegrad.
      </p>
      <ol>
        <li>Im Reiter <strong>✅ Prüffragen</strong> die Fragen Thema für Thema beantworten.</li>
        <li>Bei „Nein" einen <strong>Nachweis anfügen</strong>, ein <strong>Issue anlegen</strong> oder die Lücke <strong>als Risiko übernehmen</strong>.</li>
        <li>Die <strong>🤖 Assistenten</strong> helfen mit KI-Prompts und nutzen vorhandene Firmen-Nachweise.</li>
        <li>Den Stand im <strong>📊 Dashboard</strong> verfolgen und als <strong>📄 Bericht</strong> exportieren.</li>
      </ol>
      <p class="hint">
        💡 KI-gestützte Auswertung finden Sie im Reiter
        <strong>🤖 Assistenten</strong>.
      </p>
    </div>

    <!-- Katalog-Version -->
    <div class="catalog-card">
      <h3>📚 BSI-Katalog</h3>
      <div class="catalog-meta">
        <div class="meta-item">
          <span class="meta-lbl">Version</span>
          <span class="meta-val">{{ catalogStatus?.version || '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-lbl">Themen</span>
          <span class="meta-val">{{ catalogStatus?.anzahl_themen ?? '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-lbl">Prüffragen</span>
          <span class="meta-val">{{ catalogStatus?.anzahl_prueffragen ?? '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-lbl">Importiert am</span>
          <span class="meta-val">{{ formatDate(catalogStatus?.imported_at) }}</span>
        </div>
      </div>
      <p v-if="!catalogStatus?.version" class="warn">
        ⚠️ Noch kein Katalog importiert. Ein Administrator kann ihn unter
        „Admin → WiBA-Katalog" herunterladen und importieren.
      </p>
    </div>

    <!-- Themen-Übersicht (read-only) -->
    <div class="themen-card">
      <h3>📋 Themenübersicht ({{ store.themen.length }})</h3>
      <div v-if="store.themen.length === 0" class="empty">
        Keine Themen geladen — bitte zuerst ein Projekt auswählen.
      </div>
      <div v-else class="thema-list">
        <details v-for="t in store.themen" :key="t.theme_key" class="thema">
          <summary>
            <span class="thema-titel">{{ t.titel }}</span>
            <span class="thema-count">{{ t.prueffragen.length }} Prüffragen</span>
          </summary>
          <div class="thema-body">
            <p v-if="t.ziel" class="thema-ziel"><strong>Ziel:</strong> {{ t.ziel }}</p>
            <p v-if="t.hinweis" class="thema-hinweis">{{ t.hinweis }}</p>
            <div v-if="t.bausteine?.length" class="bausteine">
              <strong>BSI-Bausteine:</strong>
              <span v-for="b in t.bausteine" :key="b" class="baustein-tag">{{ b }}</span>
            </div>
            <p v-if="t.weiterfuehrend" class="weiterfuehrend">
              🔗 Weiterführend: {{ t.weiterfuehrend }}
            </p>
          </div>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useWibaStore } from '../../stores/wiba'

const store = useWibaStore()
const catalogStatus = computed(() => store.catalogStatus)

const formatDate = (s?: string): string => {
  if (!s) return '—'
  try {
    return new Date(s).toLocaleString('de-DE')
  } catch {
    return s
  }
}

onMounted(() => {
  if (!store.catalogStatus) store.fetchCatalogStatus()
})
</script>

<style scoped>
.wiba-doku { display: flex; flex-direction: column; gap: 16px; }

.intro-banner {
  background: #e3f2fd; border-left: 4px solid #1565c0;
  padding: 16px 20px; border-radius: 8px;
}
.intro-banner h3 { margin: 0 0 8px; color: #0d47a1; }
.intro-banner p { margin: 0 0 8px; color: #333; line-height: 1.5; }
.intro-banner ol { margin: 8px 0; padding-left: 20px; line-height: 1.7; color: #333; }
.intro-banner .hint { color: #1565c0; font-size: 13px; margin-bottom: 0; }

.catalog-card, .themen-card {
  background: white; border: 1px solid var(--color-border); border-radius: 8px; padding: 16px 20px;
}
.catalog-card h3, .themen-card h3 { margin: 0 0 12px; font-size: 16px; }

.catalog-meta { display: flex; gap: 24px; flex-wrap: wrap; }
.meta-item { display: flex; flex-direction: column; gap: 2px; }
.meta-lbl { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.04em; }
.meta-val { font-size: 16px; font-weight: 700; color: var(--color-primary, #1565c0); }
.warn {
  margin: 12px 0 0; background: #fff8e1; color: #e65100;
  padding: 8px 12px; border-radius: 4px; font-size: 13px; border: 1px solid #ffd54f;
}

.empty { padding: 24px; text-align: center; color: #888; }

.thema-list { display: flex; flex-direction: column; gap: 6px; }
.thema {
  border: 1px solid var(--color-border); border-radius: 6px; background: #fafbfc;
}
.thema summary {
  cursor: pointer; padding: 10px 14px; display: flex; justify-content: space-between;
  align-items: center; gap: 12px; font-weight: 600;
}
.thema-titel { color: var(--color-text-primary, #222); }
.thema-count { font-size: 12px; color: #888; font-weight: 400; }
.thema-body { padding: 0 14px 12px; font-size: 13px; color: #444; }
.thema-ziel { margin: 8px 0; }
.thema-hinweis { margin: 4px 0; color: #555; }
.bausteine { margin: 8px 0; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.baustein-tag {
  background: #e3f2fd; color: #1565c0; padding: 1px 8px;
  border-radius: 10px; font-size: 11px; font-weight: 600; font-family: monospace;
}
.weiterfuehrend { margin: 8px 0 0; font-size: 12px; color: #1565c0; }
</style>
