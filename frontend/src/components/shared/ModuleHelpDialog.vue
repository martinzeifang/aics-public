<!--
  ModuleHelpDialog (#926/#927) — strukturierter Hilfe-Dialog je Modul:
  Zweck, gesetzlicher Rahmen, allgemeine Umsetzungshinweise, modul-spezifisches,
  optional Framework-Übersicht (Risikobewertung) + weiterführende Links.
-->
<template>
  <div v-if="open" class="mh-overlay" @mousedown.self="$emit('close')" role="dialog" aria-modal="true">
    <div class="mh-modal">
      <header class="mh-header">
        <div>
          <h2>❓ Hilfe — {{ help?.title || 'Modul' }}</h2>
          <p v-if="help?.regulation" class="mh-reg">{{ help.regulation }}</p>
        </div>
        <button class="mh-close" type="button" aria-label="Schließen" @click="$emit('close')">✕</button>
      </header>

      <div class="mh-body">
        <p v-if="!help" class="mh-empty">Für dieses Modul ist noch keine Hilfe hinterlegt.</p>

        <template v-else>
          <p v-if="help.purpose" class="mh-purpose">{{ help.purpose }}</p>

          <section v-for="sec in sections" :key="sec.title" class="mh-section">
            <h3>{{ sec.title }}</h3>
            <p v-if="sec.intro" class="mh-intro">{{ sec.intro }}</p>
            <ul v-if="sec.bullets && sec.bullets.length">
              <li v-for="(b, i) in sec.bullets" :key="i">{{ b }}</li>
            </ul>
          </section>

          <section v-if="help.frameworks && help.frameworks.length" class="mh-section">
            <h3>Frameworks — wann welches sinnvoll ist</h3>
            <div class="mh-fw-grid">
              <article v-for="(fw, i) in help.frameworks" :key="fw.name" class="mh-fw-card"
                       :style="{ borderTopColor: fwColor(i) }">
                <header class="mh-fw-head">
                  <span class="mh-fw-name" :style="{ color: fwColor(i) }">{{ fw.name }}</span>
                </header>
                <p class="mh-fw-ref">{{ fw.ref }}</p>
                <p class="mh-fw-when">{{ fw.whenToUse }}</p>
              </article>
            </div>
          </section>

          <section v-if="help.links && help.links.length" class="mh-section">
            <h3>Weiterführend</h3>
            <ul>
              <li v-for="l in help.links" :key="l.href">
                <a :href="l.href" target="_blank" rel="noopener noreferrer">{{ l.label }}</a>
              </li>
            </ul>
          </section>
        </template>
      </div>

      <footer class="mh-footer">
        <span class="mh-disclaimer">Allgemeine Orientierung — ersetzt keine Rechtsberatung.</span>
        <button class="mh-btn" type="button" @click="$emit('close')">Schließen</button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ModuleHelp, HelpSection } from '../../help/types'

const props = defineProps<{ open: boolean; help?: ModuleHelp | null }>()
defineEmits<{ (e: 'close'): void }>()

const sections = computed<HelpSection[]>(() => {
  const h = props.help
  if (!h) return []
  const out: HelpSection[] = [h.legalBasis, h.implementation]
  if (h.moduleSpecific) out.push(h.moduleSpecific)
  return out.filter(Boolean)
})

// #1067: Farbpalette für die Framework-Karten (stabil je Position).
const _FW_COLORS = ['#1565c0', '#2e7d32', '#c62828', '#6a1b9a', '#ef6c00', '#00838f', '#ad1457']
const fwColor = (i: number): string => _FW_COLORS[i % _FW_COLORS.length]
</script>

<style scoped>
.mh-overlay {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 1rem;
}
.mh-modal {
  background: var(--color-surface, #fff); color: var(--color-text-primary, #1a1a1a);
  border-radius: 10px; width: min(820px, 100%); max-height: 90vh;
  display: flex; flex-direction: column; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25);
}
.mh-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  background: #1565c0; color: #fff; padding: 0.9rem 1.2rem; border-radius: 10px 10px 0 0;
}
.mh-header h2 { margin: 0; font-size: 1.15rem; }
.mh-reg { margin: 0.2rem 0 0; font-size: 0.82rem; color: #bbdefb; }
.mh-close { background: none; border: none; color: #fff; font-size: 1.2rem; cursor: pointer; }
.mh-body { overflow-y: auto; padding: 1rem 1.2rem; }
.mh-purpose { font-size: 0.92rem; color: #37474f; margin: 0 0 1rem; }
.mh-section { margin-bottom: 1.1rem; }
.mh-section h3 { font-size: 1rem; color: #0d47a1; margin: 0 0 0.4rem; border-bottom: 1px solid #e3f2fd; padding-bottom: 0.2rem; }
.mh-intro { font-size: 0.88rem; color: #455a64; margin: 0 0 0.5rem; }
.mh-section ul { margin: 0.2rem 0 0; padding-left: 1.2rem; }
.mh-section li { font-size: 0.86rem; margin-bottom: 0.25rem; line-height: 1.4; }
/* #1067: Framework-Übersicht als farbige Karten (statt enger Tabelle) */
.mh-fw-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 0.7rem;
}
.mh-fw-card {
  border: 1px solid #e0e0e0; border-top: 3px solid #1565c0; border-radius: 8px;
  padding: 0.6rem 0.8rem; background: #fafbfc;
  display: flex; flex-direction: column; gap: 0.3rem;
}
.mh-fw-head { display: flex; align-items: center; }
.mh-fw-name { font-weight: 700; font-size: 0.95rem; }
.mh-fw-ref { color: #78909c; font-size: 0.74rem; margin: 0; line-height: 1.35; }
.mh-fw-when { color: #37474f; font-size: 0.83rem; margin: 0; line-height: 1.45; }
.mh-footer {
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  padding: 0.7rem 1.2rem; border-top: 1px solid var(--color-border, #e0e0e0);
}
.mh-disclaimer { font-size: 0.76rem; color: #90a4ae; }
.mh-btn { background: #1565c0; color: #fff; border: none; border-radius: 6px; padding: 0.45rem 1rem; cursor: pointer; font-size: 0.85rem; }
.mh-empty { color: #78909c; }
</style>
