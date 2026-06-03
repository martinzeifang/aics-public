<template>
  <div class="dashboard">
    <div class="page-header">
      <h1>Welcome, {{ userDisplayName }}</h1>
      <p class="page-subtitle">Select a module to get started</p>
    </div>

    <div class="dashboard-grid">
      <!-- CRA Module -->
      <div v-if="authStore.hasPermission('cra:read')" class="module-card card">
        <div class="module-icon cra-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z"></path>
          </svg>
        </div>
        <h3>CRA Readiness</h3>
        <p class="module-description">Compliance Risk Assessment based on OWASP Proactive Controls</p>
        <router-link to="/cra" class="btn btn-primary">Open Module</router-link>
      </div>

      <!-- DSGVO Module -->
      <div class="module-card card disabled">
        <div class="module-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7v10c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-10-5z"></path>
          </svg>
        </div>
        <h3>DSGVO Readiness</h3>
        <p class="module-description">GDPR and data protection compliance</p>
        <span class="coming-soon-badge">Coming in Phase-2</span>
      </div>

      <!-- NIS2 Module -->
      <div class="module-card card disabled">
        <div class="module-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
            <line x1="12" y1="22.08" x2="12" y2="12"></line>
          </svg>
        </div>
        <h3>NIS2 Readiness</h3>
        <p class="module-description">NIS2 Directive compliance assessment</p>
        <span class="coming-soon-badge">Coming in Phase-2</span>
      </div>

      <!-- Admin Users Module -->
      <div v-if="authStore.hasPermission('admin:users')" class="module-card card">
        <div class="module-icon admin-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
            <circle cx="9" cy="7" r="4"></circle>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
          </svg>
        </div>
        <h3>User Management</h3>
        <p class="module-description">Manage system users and permissions</p>
        <router-link to="/admin/users" class="btn btn-primary">Manage Users</router-link>
      </div>
    </div>

    <!-- Quick Stats -->
    <section class="quick-stats card">
      <h2>Quick Statistics</h2>
      <div class="stats-grid">
        <div class="stat">
          <span class="stat-label">Modules Active</span>
          <span class="stat-value">{{ activeModules }}</span>
        </div>
        <div class="stat">
          <span class="stat-label">Your Role</span>
          <span class="stat-value badge" :class="`role-${userRole}`">{{ userRole }}</span>
        </div>
        <div class="stat">
          <span class="stat-label">Last Login</span>
          <span class="stat-value">Today</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()

const userDisplayName = computed(() => {
  const email = authStore.user?.email || 'User'
  return email.split('@')[0]
})

const userRole = computed(() => {
  const roles = authStore.user?.roles || []
  if (roles.includes('admin')) return 'admin'
  if (roles.includes('editor')) return 'editor'
  return 'viewer'
})

const activeModules = computed(() => {
  let count = 0
  if (authStore.hasPermission('cra:read')) count++
  if (authStore.hasPermission('admin:users')) count++
  return count
})
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: var(--spacing-xl);
}

.page-header h1 {
  color: var(--color-primary);
  margin-bottom: var(--spacing-sm);
  font-size: var(--font-size-2xl);
}

.page-subtitle {
  color: var(--color-text-secondary);
  margin: 0;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

.module-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--spacing-xl);
  position: relative;
  transition: all var(--transition-base);
}

.module-card:not(.disabled):hover {
  transform: translateY(-8px);
  box-shadow: var(--shadow-lg);
}

.module-card.disabled {
  opacity: 0.6;
  cursor: not-allowed;
  background: #fafafa;
}

.module-icon {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--spacing-lg);
  color: white;
}

.module-icon.cra-icon {
  background: linear-gradient(135deg, #1565c0, #0d47a1);
}

.module-icon.admin-icon {
  background: linear-gradient(135deg, #f57c00, #e65100);
}

.module-card h3 {
  color: var(--color-primary);
  margin: 0 0 var(--spacing-sm) 0;
  font-size: var(--font-size-lg);
}

.module-description {
  color: var(--color-text-secondary);
  margin: 0 0 var(--spacing-lg) 0;
  font-size: var(--font-size-sm);
  line-height: 1.5;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: 6px;
  text-decoration: none;
  font-weight: 500;
  transition: all var(--transition-base);
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover {
  background: var(--color-primary-dark);
}

.coming-soon-badge {
  display: inline-block;
  background: #fff3e0;
  color: #e65100;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: 4px;
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
}

/* Quick Stats */
.quick-stats {
  padding: var(--spacing-xl);
}

.quick-stats h2 {
  color: var(--color-primary);
  margin-bottom: var(--spacing-lg);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-lg);
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-lg);
  background: var(--color-background);
  border-radius: 8px;
  border: 1px solid var(--color-border);
}

.stat-label {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  margin-bottom: var(--spacing-sm);
  text-transform: uppercase;
  font-weight: 600;
}

.stat-value {
  color: var(--color-primary);
  font-size: var(--font-size-xl);
  font-weight: 600;
}

.badge {
  display: inline-block;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: 4px;
  font-size: var(--font-size-sm);
  text-transform: capitalize;
}

.role-admin {
  background: #e3f2fd;
  color: #1565c0;
}

.role-editor {
  background: #fff3e0;
  color: #e65100;
}

.role-viewer {
  background: #f0f0f0;
  color: #666;
}

@media (max-width: 768px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .page-header h1 {
    font-size: var(--font-size-xl);
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
