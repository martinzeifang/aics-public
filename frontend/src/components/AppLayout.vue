<template>
  <div class="app-layout">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <button
          class="menu-toggle"
          @click="sidebarOpen = !sidebarOpen"
          title="Menü"
          aria-label="Sidebar umschalten"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3 6h18v2H3V6m0 5h18v2H3v-2m0 5h18v2H3v-2z" />
          </svg>
        </button>
        <img src="/logo_header.png" alt="Logo" class="logo" />
        <div class="header-title">
          <h1>AI Compliance Suite</h1>
          <p>Compliance Management Platform</p>
        </div>
      </div>

      <div class="header-right">
        <button class="btn-icon" @click="themeStore.toggle()"
                :title="themeStore.theme === 'dark' ? 'Light Mode' : 'Dark Mode'">
          <svg v-if="themeStore.theme === 'dark'" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5M2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1m18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1M11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1m0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1M5.99 4.58a.996.996 0 0 0-1.41 0c-.39.39-.39 1.03 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0s.39-1.03 0-1.41z"/>
          </svg>
          <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M9 2c-1.05 0-2.05.16-3 .46 4.06 1.27 7 5.06 7 9.54 0 4.48-2.94 8.27-7 9.54.95.3 1.95.46 3 .46 5.52 0 10-4.48 10-10S14.52 2 9 2"/>
          </svg>
        </button>
        <router-link v-if="isAdmin" to="/admin"
                     class="btn-icon" title="Administration"
                     :class="{ active: $route.path.startsWith('/admin') }">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/>
          </svg>
        </router-link>
        <LanguageSwitcher />
        <!-- Zahnrad-Button entfernt — Einstellungen via Admin → ⚙ Einstellungen -->

        <!-- KI-Provider-Badge (Sprint #16, #867): aktiver Provider + Egress-Status -->
        <AIProviderBadge />

        <div class="user-menu" ref="userMenuRef">
          <span class="user-email">{{ authStore.user?.email }}</span>
          <div class="dropdown" :class="{ open: userDropdownOpen }">
            <button class="btn-user" title="Benutzer" @click.stop="userDropdownOpen = !userDropdownOpen">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
              </svg>
            </button>
            <div class="dropdown-menu" v-show="userDropdownOpen" @click.stop>
              <button @click="$router.push('/admin/settings'); userDropdownOpen = false" class="dropdown-item">Einstellungen</button>
              <button @click="goToSecurity" class="dropdown-item">🔐 Sicherheit (2FA)</button>
              <hr />
              <button @click="logout" class="dropdown-item logout-item">Abmelden</button>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- Lizenz-Banner (Issue #369 + Named-User #395) -->
    <div v-if="licenseBanner" :class="['license-banner', licenseBannerKind]">
      <span class="license-banner-icon">{{ licenseBannerIcon }}</span>
      <span class="license-banner-text">{{ licenseBanner }}</span>
      <router-link v-if="isAdmin" to="/admin/license" class="license-banner-link">
        → Lizenz verwalten
      </router-link>
    </div>

    <!-- Module Navigation (Horizontal) -->
    <nav class="module-nav">
      <button
        v-for="module in visibleModules"
        :key="module.id"
        @click="selectModule(module.id)"
        :class="['module-btn', { active: currentModule === module.id }]"
        :title="module.tooltip"
      >
        {{ module.label }}
      </button>
    </nav>

    <!-- Main Content Area -->
    <div class="main-container">
      <!-- Issue #389: im Admin-Bereich keine Modul-Sidebar einblenden -->
      <aside v-if="!isAdminRoute" class="app-sidebar" :class="{ open: sidebarOpen }">
        <component :is="currentSidebarComponent" :key="currentModule" />
      </aside>

      <main class="app-main">
        <router-view :key="$route.fullPath" />
      </main>
    </div>

    <!-- Mobile Sidebar Overlay -->
    <div v-if="sidebarOpen" class="sidebar-overlay" @click="sidebarOpen = false" />

    <!-- Status Bar -->
    <StatusBar />

    <!-- Settings Dialog -->
    <!-- SettingsDialog wurde in /admin/settings migriert; Legacy-Modal entfernt -->
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/theme'
import { useAdminStore } from '../stores/admin'
import { useRouter, useRoute } from 'vue-router'
import KundenSidebar from './sidebars/KundenSidebar.vue'
import RisikobewertungSidebar from './sidebars/RisikobewertungSidebar.vue'
import CRASidebar from './sidebars/CRASidebar.vue'
import DSGVOSidebar from './sidebars/DSGVOSidebar.vue'
import NIS2Sidebar from './sidebars/NIS2Sidebar.vue'
import DORASidebar from './sidebars/DORASidebar.vue'
import GutachtenSidebar from './sidebars/GutachtenSidebar.vue'
import AIActSidebar from './sidebars/AIActSidebar.vue'
import StatusBar from './StatusBar.vue'
// SettingsDialog wird jetzt nur noch in AdminSettingsView eingebettet
import LanguageSwitcher from './LanguageSwitcher.vue'
import AIProviderBadge from './shared/AIProviderBadge.vue'

const authStore = useAuthStore()
const themeStore = useThemeStore()
const adminStore = useAdminStore()
const router = useRouter()
const route = useRoute()
const sidebarOpen = ref(false)
// settingsOpen entfernt — Einstellungen leben jetzt unter /admin/settings
const userDropdownOpen = ref(false)
const userMenuRef = ref<HTMLElement | null>(null)

const onOutsideClick = (e: MouseEvent) => {
  if (!userDropdownOpen.value) return
  const el = userMenuRef.value
  if (el && !el.contains(e.target as Node)) {
    userDropdownOpen.value = false
  }
}
const onEscape = (e: KeyboardEvent) => {
  if (e.key === 'Escape') userDropdownOpen.value = false
}
onMounted(() => {
  document.addEventListener('click', onOutsideClick)
  document.addEventListener('keydown', onEscape)
  // Issue #388: Modul-Disable wirkt erst nach Settings-Load
  if (authStore.user?.roles?.includes('admin') && !adminStore.settings) {
    adminStore.fetchSettings()
  }
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onOutsideClick)
  document.removeEventListener('keydown', onEscape)
})

const isAdmin = computed(() => authStore.user?.roles?.includes('admin') ?? false)
const isAdminRoute = computed(() => route.path.startsWith('/admin') || route.path.startsWith('/account'))

// Lizenz-Banner (Issues #369, #395)
const licenseInfo = computed<any>(() => (authStore.user as any)?.license_state || {})
const licenseBanner = computed(() => {
  const st = licenseInfo.value
  if (!st || !st.state) return ''
  if (st.state === 'read-only') {
    return `Lizenz-Verstoß: ${st.reason || 'Lizenz nicht gültig'}. Schreibzugriff ist gesperrt.`
  }
  if (st.over_limit) {
    return `Ihre Organisation überschreitet das Lizenz-User-Limit (max ${st.max_users}). Administrator kontaktieren.`
  }
  if (st.state === 'demo' && st.expires_at) {
    const daysLeft = Math.max(0, Math.round((st.expires_at * 1000 - Date.now()) / 86400000))
    if (daysLeft <= 7) {
      return `Demo-Lizenz läuft in ${daysLeft} Tagen ab. Bitte Lizenz aktivieren.`
    }
  }
  return ''
})
const licenseBannerKind = computed(() => {
  const st = licenseInfo.value
  if (st?.state === 'read-only') return 'critical'
  if (st?.over_limit) return 'warning'
  return 'info'
})
const licenseBannerIcon = computed(() =>
  licenseBannerKind.value === 'critical' ? '⛔' : licenseBannerKind.value === 'warning' ? '⚠' : 'ℹ',
)

const visibleModules = computed(() => {
  let list = modules
  const allowed = authStore.user?.allowed_modules
  if (allowed && Array.isArray(allowed) && allowed.length > 0) {
    list = list.filter(m => allowed.includes(m.id))
  }
  // Issue #388: in den Einstellungen deaktivierte Module ausblenden
  const disabledFromProfile = (authStore.user as any)?.disabled_modules || []
  const disabledFromAdmin = adminStore.settings?.modules?.disabled || []
  const disabled = Array.from(new Set([...disabledFromProfile, ...disabledFromAdmin]))
  if (disabled.length > 0) {
    list = list.filter(m => !disabled.includes(m.id))
  }
  // #413: Lizenz-Whitelist strikt anwenden.
  //   - 'kunden' ist immer sichtbar (Master-Modul)
  //   - 'gutachten' ist nur sichtbar, wenn EXPLIZIT in der Liste — '*' allein reicht NICHT
  //   - alle anderen Module: wenn Liste explizit, müssen sie drin sein;
  //     wenn '*'-Wildcard, sind sie sichtbar
  //   - leere Liste / nicht-Array (= keine Lizenz aktiv): nur 'kunden'
  const licMods = (authStore.user as any)?.license_modules
  console.info('[AppLayout] license_modules =', licMods, '| user-Object:', authStore.user)
  if (Array.isArray(licMods)) {
    const hasWildcard = licMods.includes('*')
    list = list.filter(m => {
      if (m.id === 'kunden') return true
      if (m.id === 'gutachten') return licMods.includes('gutachten')
      return hasWildcard || licMods.includes(m.id)
    })
  } else {
    console.warn('[AppLayout] license_modules ist kein Array — Filter inaktiv. Re-Login oder loadProfile() nötig.')
  }
  return list
})

const modules = [
  { id: 'kunden', label: 'Kunden', tooltip: 'Kundenverwaltung' },
  { id: 'risikobewertung', label: 'Risikobewertung', tooltip: 'Multi-Framework-Risikobewertung' },
  { id: 'cra', label: 'CRA', tooltip: 'Cyber Resilience Act (EU 2024/2847)' },
  { id: 'nis2', label: 'NIS2', tooltip: 'NIS2-Richtlinie' },
  { id: 'dora', label: 'DORA', tooltip: 'Digital Operational Resilience Act' },
  { id: 'aiact', label: 'AI Act', tooltip: 'EU AI Act (EU 2024/1689)' },
  { id: 'dsgvo', label: 'DSGVO', tooltip: 'GDPR / DSGVO' },
  { id: 'gutachten', label: 'Gutachten', tooltip: 'Expert Opinions' },
]

const currentModule = computed(() => {
  const path = route.path.split('/')[1]
  return path || 'kunden'
})

const sidebarComponents: Record<string, any> = {
  kunden: KundenSidebar,
  risikobewertung: RisikobewertungSidebar,
  cra: CRASidebar,
  dsgvo: DSGVOSidebar,
  nis2: NIS2Sidebar,
  dora: DORASidebar,
  gutachten: GutachtenSidebar,
  aiact: AIActSidebar,
}

const currentSidebarComponent = computed(() => {
  return sidebarComponents[currentModule.value] || KundenSidebar
})

const selectModule = (moduleId: string) => {
  router.push(`/${moduleId}`)
  sidebarOpen.value = false
}

const logout = () => {
  authStore.logout()
  router.push('/login')
}

const goToSecurity = () => {
  userDropdownOpen.value = false
  router.push('/account/security')
}
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: var(--color-background);
}

/* Header */
.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 60px;
  background: linear-gradient(135deg, var(--color-primary) 0%, #0d47a1 100%);
  color: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
  box-shadow: var(--shadow-md);
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.menu-toggle {
  display: none;
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  width: 36px;
  height: 36px;
  border-radius: 4px;
  cursor: pointer;
  align-items: center;
  justify-content: center;
}

.logo {
  height: 40px;
  width: auto;
}

.header-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.header-title h1 {
  margin: 0;
  font-size: 16px;
  line-height: 1.1;
  font-weight: 600;
}

.header-title p {
  margin: 0;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.8);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-icon {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-icon:hover {
  background: rgba(255, 255, 255, 0.3);
}
.btn-icon.active {
  background: rgba(255, 255, 255, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.5);
}
.btn-icon { text-decoration: none; }

.user-menu {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
}

.user-email {
  font-size: 13px;
}

.btn-user {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.btn-user:hover {
  background: rgba(255, 255, 255, 0.3);
}

.dropdown {
  position: relative;
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  background: var(--color-surface);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  min-width: 200px;
  box-shadow: var(--shadow-lg);
  z-index: 1000;
  padding: 4px 0;
}

.dropdown-item {
  display: block;
  width: 100%;
  padding: 10px 14px;
  border: none;
  background: none;
  color: var(--color-text-primary);
  text-align: left;
  cursor: pointer;
  text-decoration: none;
  font-size: 13px;
}

.dropdown-item:hover {
  background: var(--color-background);
  color: var(--color-primary);
}

.dropdown-item.logout-item {
  color: var(--color-error);
}

.dropdown-item.logout-item:hover {
  background: #ffebee;
}

.dropdown-menu hr {
  margin: 0;
  border: none;
  border-top: 1px solid var(--color-border);
}

.dropdown-section {
  padding: 6px 14px 4px;
  font-size: 11px;
  text-transform: uppercase;
  color: #888;
  font-weight: 600;
  letter-spacing: 0.5px;
}

/* Module Navigation */
.license-banner {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px 20px;
  font-size: 13px;
  border-bottom: 1px solid;
}
.license-banner.critical { background: #ffebee; color: #c62828; border-color: #ef9a9a; }
.license-banner.warning  { background: #fff8e1; color: #f57c00; border-color: #ffe082; }
.license-banner.info     { background: #e3f2fd; color: #1565c0; border-color: #90caf9; }
.license-banner-icon { font-size: 16px; }
.license-banner-link { margin-left: auto; color: inherit; text-decoration: underline; font-weight: 500; }

.module-nav {
  position: fixed;
  top: 60px;
  left: 0;
  right: 0;
  height: 44px;
  background: white;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 2px;
  overflow-x: auto;
  overflow-y: hidden;
  z-index: 99;
}

.module-btn {
  padding: 8px 14px;
  border: none;
  background: none;
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  border-bottom: 3px solid transparent;
  border-radius: 4px 4px 0 0;
  transition: all 0.2s;
}

.module-btn:hover {
  color: var(--color-primary);
  background: var(--color-background);
}

.module-btn.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  background: #e3f2fd;
}

/* Main Container */
.main-container {
  display: flex;
  flex: 1;
  margin-top: 104px;
  margin-bottom: 28px;
  overflow: hidden;
}

.app-sidebar {
  width: 260px;
  flex-shrink: 0;
  background: white;
  border-right: 1px solid var(--color-border);
  overflow-y: auto;
  padding: 16px;
  box-shadow: inset -1px 0 0 var(--color-border);
}

.app-main {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  background: var(--color-background);
}

.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 98;
  display: none;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  padding: 24px;
  max-width: 400px;
  width: 90%;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  margin-top: 12px;
}

/* Mobile */
@media (max-width: 1024px) {
  .menu-toggle {
    display: flex;
  }

  .header-title p {
    display: none;
  }

  .user-email {
    display: none;
  }

  .app-sidebar {
    position: fixed;
    left: 0;
    top: 104px;
    bottom: 28px;
    height: calc(100vh - 104px - 28px);
    width: 280px;
    transform: translateX(-100%);
    transition: transform 0.25s ease-out;
    z-index: 99;
  }

  .app-sidebar.open {
    transform: translateX(0);
  }

  .sidebar-overlay {
    display: block;
  }

  .app-main {
    padding: 12px;
  }
}

@media (max-width: 480px) {
  .logo {
    height: 32px;
  }

  .header-title h1 {
    font-size: 14px;
  }
}
</style>
