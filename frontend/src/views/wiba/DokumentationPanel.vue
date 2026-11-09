<template>
  <div class="wiba-doku">
    <!-- Intro / Hier starten -->
    <div class="intro-banner">
      <h3>{{ $t('wiba.dokumentationPanel.hierStartenWiBAWegInDieBasisAbsicher') }}</h3>
      <p>
        {{ $t('wiba.dokumentationPanel.wiBAIstDerVomBSIEmpfohleneEinstiegIn') }} <strong>{{ $t('wiba.dokumentationPanel.pruffragen') }}</strong> {{ $t('wiba.dokumentationPanel.zuDenWichtigstenThemenPrufenSieObGru') }} <strong>Ja</strong>,
        <strong>{{ $t('common.no') }}</strong> {{ $t('wiba.dokumentationPanel.oder') }} <strong>{{ $t('common.nichtRelevant') }}</strong> {{ $t('wiba.dokumentationPanel.darausErgibtSichIhrReifegrad') }}
      </p>
      <ol>
        <li>{{ $t('wiba.dokumentationPanel.imReiter') }} <strong>{{ $t('wiba.dokumentationPanel.pruffragen2') }}</strong> {{ $t('wiba.dokumentationPanel.dieFragenThemaFurThemaBeantworten') }}</li>
        <li>{{ $t('wiba.dokumentationPanel.beiNeinEinen') }} <strong>{{ $t('wiba.dokumentationPanel.nachweisAnfugen') }}</strong>{{ $t('wiba.dokumentationPanel.ein') }} <strong>{{ $t('wiba.dokumentationPanel.issueAnlegen') }}</strong> {{ $t('wiba.dokumentationPanel.oderDieLucke') }} <strong>{{ $t('wiba.dokumentationPanel.alsRisikoUbernehmen') }}</strong>.</li>
        <li>{{ $t('wiba.dokumentationPanel.die') }} <strong>{{ $t('wiba.dokumentationPanel.assistenten') }}</strong> {{ $t('wiba.dokumentationPanel.helfenMitKIPromptsUndNutzenVorhanden') }}</li>
        <li>{{ $t('wiba.dokumentationPanel.denStandIm') }} <strong>{{ $t('wiba.dokumentationPanel.dashboard') }}</strong> {{ $t('wiba.dokumentationPanel.verfolgenUndAls') }} <strong>{{ $t('wiba.dokumentationPanel.bericht') }}</strong> {{ $t('wiba.dokumentationPanel.exportieren') }}</li>
      </ol>
      <p class="hint">
        {{ $t('wiba.dokumentationPanel.kIGestutzteAuswertungFindenSieImReit') }}
        <strong>{{ $t('wiba.dokumentationPanel.assistenten') }}</strong>.
      </p>
    </div>

    <!-- Katalog-Version -->
    <div class="catalog-card">
      <h3>{{ $t('wiba.dokumentationPanel.bSIKatalog') }}</h3>
      <div class="catalog-meta">
        <div class="meta-item">
          <span class="meta-lbl">{{ $t('common.version') }}</span>
          <span class="meta-val">{{ catalogStatus?.version || '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-lbl">{{ $t('wiba.dokumentationPanel.themen') }}</span>
          <span class="meta-val">{{ catalogStatus?.anzahl_themen ?? '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-lbl">{{ $t('wiba.dokumentationPanel.pruffragen') }}</span>
          <span class="meta-val">{{ catalogStatus?.anzahl_prueffragen ?? '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-lbl">{{ $t('wiba.dokumentationPanel.importiertAm') }}</span>
          <span class="meta-val">{{ formatDate(catalogStatus?.imported_at) }}</span>
        </div>
      </div>
      <p v-if="!catalogStatus?.version" class="warn">
        {{ $t('wiba.dokumentationPanel.nochKeinKatalogImportiertEinAdminist') }}
      </p>
    </div>

    <!-- Themen-Übersicht (read-only) -->
    <div class="themen-card">
      <h3>{{ $t('wiba.dokumentationPanel.themenubersichtV0', { v0: store.themen.length }) }}</h3>
      <div v-if="store.themen.length === 0" class="empty">
        <template v-if="!store.selectedProjekt">{{ $t('wiba.dokumentationPanel.bitteLinksEinWiBAProjektAuswahlen') }}</template>
        <template v-else>{{ $t('wiba.dokumentationPanel.derBSIWiBAKatalogIstAufDieserInstall') }}</template>
      </div>
      <div v-else class="thema-list">
        <details v-for="t in store.themen" :key="t.theme_key" class="thema">
          <summary>
            <span class="thema-titel">{{ t.titel }}</span>
            <span class="thema-count">{{ $t('wiba.dokumentationPanel.v0Pruffragen', { v0: t.prueffragen.length }) }}</span>
          </summary>
          <div class="thema-body">
            <p v-if="t.ziel" class="thema-ziel"><strong>{{ $t('wiba.dokumentationPanel.ziel') }}</strong> {{ t.ziel }}</p>
            <p v-if="t.hinweis" class="thema-hinweis">{{ t.hinweis }}</p>
            <div v-if="t.bausteine?.length" class="bausteine">
              <strong>{{ $t('wiba.dokumentationPanel.bSIBausteine') }}</strong>
              <span v-for="b in bausteinChips(t.bausteine)" :key="b" class="baustein-tag">{{ b }}</span>
            </div>
            <p v-if="t.weiterfuehrend" class="weiterfuehrend">
              {{ $t('wiba.dokumentationPanel.weiterfuhrendV0', { v0: t.weiterfuehrend }) }}
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
const bausteinChips = (s?: string): string[] =>
  (s || '').split(';').map((x) => x.trim()).filter(Boolean)

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
