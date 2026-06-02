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
            <table class="mh-fw">
              <thead><tr><th>Framework</th><th>Bezug</th><th>Wann sinnvoll</th></tr></thead>
              <tbody>
                <tr v-for="fw in help.frameworks" :key="fw.name">
                  <td class="mh-fw-name">{{ fw.name }}</td>
                  <td class="mh-fw-ref">{{ fw.ref }}</td>
                  <td>{{ fw.whenToUse }}</td>
                </tr>
              </tbody>
            </table>
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
.mh-fw { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
.mh-fw th, .mh-fw td { text-align: left; padding: 0.4rem 0.5rem; border-bottom: 1px solid #eee; vertical-align: top; }
.mh-fw th { color: #607d8b; text-transform: uppercase; font-size: 0.74rem; }
.mh-fw-name { font-weight: 600; color: #1565c0; white-space: nowrap; }
.mh-fw-ref { color: #78909c; white-space: nowrap; }
.mh-footer {
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  padding: 0.7rem 1.2rem; border-top: 1px solid var(--color-border, #e0e0e0);
}
.mh-disclaimer { font-size: 0.76rem; color: #90a4ae; }
.mh-btn { background: #1565c0; color: #fff; border: none; border-radius: 6px; padding: 0.45rem 1rem; cursor: pointer; font-size: 0.85rem; }
.mh-empty { color: #78909c; }
</style>
