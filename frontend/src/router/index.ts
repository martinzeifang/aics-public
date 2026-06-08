import { createRouter, createWebHistory, type RouteRecordRaw, type RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '../stores/auth'

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

  // DORA Module (Phase 5.6 placeholder)
  {
    path: '/dora',
    name: 'DORA',
    component: () => import('../views/dora/DORAView.vue'),
    meta: { requiresAuth: true }
  },

  // Gutachten Module
  {
    path: '/gutachten',
    name: 'Gutachten',
    component: () => import('../views/gutachten/GutachtenView.vue'),
    meta: { requiresAuth: true }
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

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
    return
  }

  if (to.meta.permission && !authStore.hasPermission(to.meta.permission as string)) {
    next('/')
    return
  }

  // #413: Lizenz-Modul-Guard. Top-Level-Pfad muss in license_modules sein.
  //   - 'firmen' immer erlaubt
  //   - 'gutachten' nur bei expliziter Nennung
  //   - '*'-Wildcard deckt alle anderen Module
  //   - leere Liste = keine Lizenz → alles außer 'firmen' gesperrt
  //   - null/undefined (alte Backend-Antwort vor Fix) = Legacy → kein Block,
  //     damit Stale-User-Data nicht zum Lockout führt
  const moduleSlug = to.path.split('/')[1]
  const LICENSED_PATHS = new Set(['cra', 'nis2', 'dora', 'aiact', 'dsgvo', 'risikobewertung', 'gutachten'])
  if (LICENSED_PATHS.has(moduleSlug)) {
    const licMods = (authStore.user as any)?.license_modules
    if (Array.isArray(licMods)) {  // strict-Modus nur bei explizitem Array
      const hasWildcard = licMods.includes('*')
      const allowed = moduleSlug === 'gutachten'
        ? licMods.includes('gutachten')
        : (hasWildcard || licMods.includes(moduleSlug))
      if (!allowed) {
        console.warn(`[router] Modul '${moduleSlug}' nicht lizenziert — Redirect zu /firmen`)
        next('/firmen')
        return
      }
    }
  }

  next()
})

export default router
