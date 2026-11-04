<template>
  <div class="status-bar">
    <div class="status-left">
      <span class="status-item">
        <span class="status-dot" :class="{ online: connected, offline: !connected }"></span>
        {{ connected ? 'Verbunden' : 'Keine Verbindung' }}
      </span>
      <span class="status-divider">|</span>
      <span class="status-item">{{ currentModuleLabel }}</span>
    </div>

    <div class="status-right">
      <!-- #1819: Lizenzüberschreitung wird hier gemeldet, nicht durch eine
           Sperre erzwungen. Der Fuß ist der richtige Ort: immer sichtbar,
           aber ohne die Arbeit zu unterbrechen. -->
      <component
        :is="istAdmin ? 'router-link' : 'span'"
        v-if="lizenzHinweis"
        :to="istAdmin ? '/admin/license' : undefined"
        class="status-item lizenz-hinweis"
        :title="lizenzTitel"
      >
        ⚠ {{ lizenzHinweis }}
      </component>
      <span class="status-divider" v-if="lizenzHinweis">|</span>
      <span class="status-item" v-if="authStore.user">
        Rolle: <strong>{{ authStore.user.roles?.[0] || 'user' }}</strong>
      </span>
      <span class="status-divider">|</span>
      <!-- #1908: Der Stand kommt vom Server, nicht aus dem Frontend-Bundle.
           `package.json` trägt den Build-Wert des Frontends — auf einem
           Dev-Image steht dort eine Release-Nummer, obwohl der Stand keine
           ist (bei v8.2.1 live passiert). Wer einen Befund dokumentiert, muss
           den Stand benennen können. -->
      <span class="status-item" :title="standTitel">
        v{{ standVersion }}
        <span v-if="standHinweis" class="stand-pille">{{ standHinweis }}</span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import apiClient from '../api/client'
// #1050: angezeigte Version aus package.json (Single Source of Truth)
import { version as appVersion } from '../../package.json'

const authStore = useAuthStore()
const route = useRoute()
const connected = ref(true)

const moduleLabels: Record<string, string> = {
  firmen: 'Firmenverwaltung',
  risikobewertung: 'Risikobewertung',
  cra: 'Cyber Resilience Act',
  dsgvo: 'DSGVO',
  nis2: 'NIS2',
  gutachten: 'Gutachten',
  aiact: 'EU AI Act',
  admin: 'Administration',
}

const currentModuleLabel = computed(() => {
  const path = route.path.split('/')[1] || ''
  return moduleLabels[path] || 'Dashboard'
})

// #1819: Die Zahlen rechnet der Server (`license_state.to_dict`) — hier wird
// nur formuliert. Die Formel im Frontend nachzubauen wäre die dritte Stelle
// mit derselben Regel (Lehre aus #1703/S9).
const lizenz = computed<any>(() => (authStore.user as any)?.license_state || {})
const istAdmin = computed(() => authStore.user?.roles?.includes('admin') ?? false)

const lizenzTeile = computed<string[]>(() => {
  const l = lizenz.value
  const teile: string[] = []
  if ((l.user_ueberhang || 0) > 0) {
    teile.push(`${l.user_count}/${l.max_users_effektiv} Benutzer`)
  }
  // Mandanten-Kontingent (#1713) — bisher stand der Überhang nur in einer
  // API-Antwort, die niemand liest.
  if (l.max_firmen > 0 && (l.aktive_mandanten || 0) > l.max_firmen) {
    teile.push(`${l.aktive_mandanten}/${l.max_firmen} Mandanten`)
  }
  return teile
})
const lizenzHinweis = computed(() =>
  lizenzTeile.value.length ? `Lizenz: ${lizenzTeile.value.join(' · ')}` : '')
// ── #1908: Stand der Installation ──────────────────────────────
const stand = computed<any>(() => (authStore.user as any)?.app_stand || null)
const standVersion = computed(() => stand.value?.version && stand.value.version !== 'unknown'
  ? stand.value.version
  : appVersion)
const standHinweis = computed(() => {
  if (stand.value?.unveroeffentlicht) return 'Entwicklungsstand'
  if (stand.value?.vorabfassung) return 'Vorabfassung'
  return ''
})
const standTitel = computed(() => {
  if (stand.value?.unveroeffentlicht) {
    return 'Diese Installation läuft auf einem unveröffentlichten Stand. Die '
      + 'Versionsangabe bezeichnet nicht den gebauten Code — für einen '
      + 'Nachweis ist ein Release nötig.'
  }
  if (stand.value?.vorabfassung) {
    return 'Vorabfassung (Beta) — veröffentlicht und signiert, aber nicht '
      + 'freigegeben. Befunde aus diesem Stand bitte als solche kennzeichnen.'
  }
  return 'Installierte Version'
})

const lizenzTitel = computed(() => {
  const l = lizenz.value
  const rechenweg = l.max_users_je_mandant > 0
    ? ` (${l.max_users} + ${l.max_users_je_mandant} je Mandant × ${l.aktive_mandanten})`
    : ''
  return `Über dem vereinbarten Kontingent${rechenweg}. `
    + 'Die Arbeit ist nicht eingeschränkt — der Überhang wird abgerechnet.'
})

let interval: number | undefined

const ping = async () => {
  try {
    await apiClient.get('/health', { timeout: 3000 })
    connected.value = true
  } catch {
    connected.value = false
  }
}

onMounted(() => {
  ping()
  interval = window.setInterval(ping, 30000)
})

onUnmounted(() => {
  if (interval) window.clearInterval(interval)
})
</script>

<style scoped>
.status-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 28px;
  background: #1565c0;
  color: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
  font-size: 12px;
  z-index: 50;
  box-shadow: 0 -1px 3px rgba(0, 0, 0, 0.1);
}

.status-left,
.status-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.status-dot.online {
  background: #4caf50;
  box-shadow: 0 0 4px #4caf50;
}

.status-dot.offline {
  background: #f44336;
}

.status-divider {
  opacity: 0.5;
}

.lizenz-hinweis {
  background: #ffb300;
  color: #3e2723;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 10px;
  text-decoration: none;
}

a.lizenz-hinweis:hover {
  background: #ffc947;
}

@media (max-width: 768px) {
  .status-bar {
    font-size: 11px;
    padding: 0 8px;
  }
  .status-divider {
    display: none;
  }
}

/* #1908: Die Kennzeichnung muss auffallen, ohne wie ein Fehler zu wirken —
   eine Vorabfassung ist ein gewollter Zustand, kein Defekt. */
.stand-pille {
  margin-left: 4px; padding: 0 5px; border-radius: 8px;
  background: #fff3e0; color: #e65100; border: 1px solid #ffcc80;
  font-size: 10px; font-weight: 600;
}
</style>
