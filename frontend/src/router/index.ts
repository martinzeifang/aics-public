import { createRouter, createWebHistory, type RouteRecordRaw, type RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { usePortalStore } from '../stores/portal'
import { istModulLizenziert } from '../utils/licenseModules'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    permission?: string
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { requiresAuth: false }
  },

  // Firmen Module
  {
    path: '/firmen',
    name: 'Firmen',
    component: () => import('../views/firmen/FirmenView.vue'),
    meta: { requiresAuth: true }
  },

  // Risikobewertung Module
  {
    path: '/risikobewertung',
    name: 'Risikobewertung',
    component: () => import('../views/risikobewertung/RisikobewertungView.vue'),
    meta: { requiresAuth: true }
  },

  // CRA Module
  {
    path: '/cra',
    name: 'CRA',
    component: () => import('../views/cra/CRAView.vue'),
    meta: { requiresAuth: true, permission: 'cra:read' }
  },

  // WiBA Module (BSI Weg in die Basis-Absicherung)
  {
    path: '/wiba',
    name: 'WiBA',
    component: () => import('../views/wiba/WiBAView.vue'),
    meta: { requiresAuth: true, permission: 'wiba:read' }
  },
  // SOC Module (Security Operations Center — Wazuh-Alarm-Triage & Incidents, #1254)
  {
    path: '/soc',
    name: 'SOC',
    component: () => import('../views/soc/SOCView.vue'),
    meta: { requiresAuth: true, permission: 'soc:read' }
  },

  // DSGVO Module
  {
    path: '/dsgvo',
    name: 'DSGVO',
    component: () => import('../views/dsgvo/DSGVOView.vue'),
    meta: { requiresAuth: true }
  },

  // NIS2 Module
  {
    path: '/nis2',
    name: 'NIS2',
    component: () => import('../views/nis2/NIS2View.vue'),
    meta: { requiresAuth: true }
  },

  // Compliance-Audit — eigenes Modul seit v7.4.0 (vorher Teil von Gutachten)
  {
    path: '/compliance-audit',
    name: 'ComplianceAudit',
    component: () => import('../views/compliance-audit/ComplianceAuditView.vue'),
    meta: { requiresAuth: true }
  },

  // Gutachten Module — /gutachten fuehrt jetzt direkt zu den Gutachten; den
  // Audit-Teil hat das eigene Modul uebernommen.
  {
    path: '/gutachten',
    redirect: '/gutachten/gerichts'
  },
  {
    path: '/gutachten/gerichts',
    name: 'Gerichtsgutachten',
    component: () => import('../views/gutachten/GerichtsgutachtenView.vue'),
    meta: { requiresAuth: true }
  },

  // AI Act Module
  {
    path: '/aiact',
    name: 'AIAct',
    component: () => import('../views/aiact/AIActView.vue'),
    meta: { requiresAuth: true }
  },

  // Account / Sicherheit (für jeden eingeloggten User)
  {
    path: '/account/security',
    name: 'AccountSecurity',
    component: () => import('../views/account/SecurityView.vue'),
    meta: { requiresAuth: true }
  },
  // Passwort-Reset Flow (#407) — beide öffentlich
  {
    path: '/account/forgot',
    name: 'AccountForgot',
    component: () => import('../views/account/ForgotPasswordView.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/account/reset',
    name: 'AccountReset',
    component: () => import('../views/account/ResetPasswordView.vue'),
    meta: { requiresAuth: false }
  },

  // Admin
  {
    path: '/admin',
    name: 'AdminDashboard',
    component: () => import('../views/admin/AdminDashboardView.vue'),
    meta: { requiresAuth: true, permission: 'admin:users' }
  },
  {
    path: '/admin/users',
    name: 'AdminUsers',
    component: () => import('../views/admin/AdminUsersView.vue'),
    meta: { requiresAuth: true, permission: 'admin:users' }
  },
  {
    path: '/admin/audit',
    name: 'AdminAudit',
    component: () => import('../views/admin/AuditLogView.vue'),
    meta: { requiresAuth: true, permission: 'admin:audit' }
  },
  {
    path: '/admin/db',
    name: 'AdminDB',
    component: () => import('../views/admin/DBViewerView.vue'),
    meta: { requiresAuth: true, permission: 'admin:audit' }
  },
  {
    path: '/admin/frameworks',
    name: 'AdminFrameworks',
    component: () => import('../views/admin/FrameworksView.vue'),
    meta: { requiresAuth: true, permission: 'admin:config' }
  },
  {
    path: '/admin/wiba-catalog',
    name: 'AdminWiBACatalog',
    component: () => import('../views/admin/WiBACatalogView.vue'),
    meta: { requiresAuth: true, permission: 'wiba:catalog' }
  },
  {
    path: '/admin/backup',
    name: 'AdminBackup',
    component: () => import('../views/admin/BackupView.vue'),
    meta: { requiresAuth: true, permission: 'admin:config' }
  },
  {
    path: '/admin/settings',
    name: 'AdminSettings',
    component: () => import('../views/admin/AdminSettingsView.vue'),
    meta: { requiresAuth: true, permission: 'admin:config' }
  },
  {
    path: '/admin/ollama',
    name: 'AdminOllamaModels',
    component: () => import('../views/admin/OllamaModelsView.vue'),
    meta: { requiresAuth: true, permission: 'admin:config' }
  },
  {
    path: '/admin/license',
    name: 'AdminLicense',
    component: () => import('../views/admin/LicenseView.vue'),
    meta: { requiresAuth: true, permission: 'admin:config' }
  },
  {
    // Sprint #50 (#1706): Mandanten-/Abrechnungsübersicht + Preisblatt
    path: '/admin/licensing',
    name: 'AdminLicensing',
    component: () => import('../views/admin/LicensingUsageView.vue'),
    meta: { requiresAuth: true, permission: 'admin:config' }
  },
  {
    path: '/admin/issues',
    name: 'AdminIssues',
    component: () => import('../views/admin/IssueOverviewView.vue'),
    meta: { requiresAuth: true, permission: 'admin:audit' }
  },
  {
    path: '/admin/templates',
    name: 'AdminTemplates',
    component: () => import('../views/admin/AdminTemplatesView.vue'),
    meta: { requiresAuth: true, permission: 'template:manage' }
  },
  {
    path: '/admin/firmen-link',
    name: 'AdminFirmenLink',
    component: () => import('../views/admin/FirmenLinkView.vue'),
    meta: { requiresAuth: true, permission: 'admin:users' }
  },

  // Legacy-Redirect (#1003): alte Lesezeichen /kunden → /firmen
  {
    path: '/kunden',
    redirect: '/firmen'
  },

  // Default redirect
  {
    path: '/',
    redirect: '/firmen'
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // #1757: Beim Neuladen liegt das Token im sessionStorage, `user` aber noch
  // nicht vor — das Profil kommt asynchron. `isAuthenticated` ist
  // `!!token && !!user`, war also im Moment der Prüfung false, und JEDER
  // Deep-Link und jedes F5 landete auf /login, obwohl die Sitzung gültig war.
  // Deshalb wird das Profil hier abgewartet, bevor entschieden wird. Ein
  // echter Auth-Fehler räumt das Token im Store ab (#1510), dann greift die
  // Prüfung darunter wie bisher.
  if (to.meta.requiresAuth && authStore.token && !authStore.user) {
    try { await authStore.loadProfile() } catch { /* unten abgefangen */ }
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
    return
  }

  // #1412: SOC-Portal — nur SOC (+ Account/Admin für Passkey/Settings) navigierbar;
  // Root + andere Modul-Routen werden auf /soc umgeleitet.
  const portalStore = usePortalStore()
  if (portalStore.isSoc && authStore.isAuthenticated) {
    const slug = to.path === '/' ? '' : (to.path.split('/')[1] || '')
    const PORTAL_ALLOWED = new Set(['soc', 'account', 'admin'])
    if (!PORTAL_ALLOWED.has(slug) && to.path !== '/soc') {
      next('/soc')
      return
    }
  }

  if (to.meta.permission && !authStore.hasPermission(to.meta.permission as string)) {
    // #1412: Im SOC-Portal /soc trotz fehlender Berechtigung durchlassen — AppLayout
    // zeigt einen freundlichen „Kein Zugriff"-Hinweis (sonst /soc↔/ Redirect-Schleife).
    if (portalStore.isSoc && to.path === '/soc') {
      next()
      return
    }
    next('/')
    return
  }

  // #413/#1712: Lizenz-Modul-Guard über denselben Helfer wie die Navigation
  // (utils/licenseModules.ts; maßgeblich shared/licensing/modules.py).
  // Vorher listete der Guard die lizenzierten Pfade hart auf — 'wiba' fehlte
  // dort, während AppLayout es ausfilterte: Navigation und Guard waren uneins.
  // Grundpreis-Module (Risikobewertung, WiBA) sind immer erlaubt, 'firmen' nie
  // gegated, und ein nicht bestätigter Lizenzstand blockiert nichts (#1510).
  const moduleSlug = to.path.split('/')[1]
  const GEGATETE_PFADE = new Set([
    'cra', 'nis2', 'aiact', 'dsgvo', 'risikobewertung', 'wiba', 'gutachten', 'soc',
    'compliance-audit',
  ])
  if (GEGATETE_PFADE.has(moduleSlug) &&
      !istModulLizenziert(moduleSlug, authStore.user)) {
    console.warn(`[router] Modul '${moduleSlug}' nicht lizenziert — Redirect zu /firmen`)
    next('/firmen')
    return
  }

  next()
})

export default router
