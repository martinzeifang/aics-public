<template>
  <div class="users-view">
    <div class="header">
      <h2>👥 Benutzerverwaltung</h2>
      <p>Konten, Rollen, Module und Berechtigungen verwalten</p>
      <button class="btn-primary" @click="startNew">+ Neuer Benutzer</button>
    </div>

    <div v-if="error" class="alert alert-error" @click="error = ''">{{ error }}</div>

    <table v-if="users.length > 0" class="users-table">
      <thead>
        <tr>
          <th>E-Mail</th>
          <th>Name</th>
          <th>Rollen</th>
          <th>Module</th>
          <th>Status</th>
          <th>Letzter Login</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td><strong>{{ u.email }}</strong></td>
          <td>{{ u.display_name || '—' }}</td>
          <td>
            <span v-for="r in u.roles" :key="r" class="role-tag">{{ r }}</span>
            <span v-if="u.roles.length === 0" class="muted">—</span>
          </td>
          <td>
            <span v-if="u.allowed_modules === null" class="muted small">aus Rolle: {{ u.effective_modules.length }}</span>
            <span v-else>
              <span v-for="m in u.allowed_modules" :key="m" class="mod-tag">{{ m }}</span>
            </span>
          </td>
          <td>
            <span :class="['status', u.active ? 'on' : 'off']">{{ u.active ? 'Aktiv' : 'Inaktiv' }}</span>
          </td>
          <td class="small">{{ formatDate(u.last_login) }}</td>
          <td>
            <button class="btn-icon" @click="openEdit(u)" title="Bearbeiten">✏️</button>
            <button class="btn-icon" @click="onDelete(u)" title="Löschen">🗑️</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-else-if="!loading" class="empty">Keine Benutzer.</div>
    <div v-if="loading" class="loading">Lade Benutzer…</div>

    <!-- Edit / Neu Dialog -->
    <div v-if="editing" class="modal-overlay" @click.self="editing = null">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>{{ editing.id ? 'Benutzer bearbeiten' : 'Neuer Benutzer' }}</h3>
          <button class="btn-close" @click="editing = null">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>E-Mail *</label>
            <input v-model="editing.email" type="email" :disabled="!!editing.id" />
          </div>
          <div class="form-row">
            <label>Anzeigename</label>
            <input v-model="editing.display_name" placeholder="z.B. Max Mustermann" />
          </div>
          <div class="form-row">
            <label>{{ editing.id ? 'Neues Passwort (leer = nicht ändern)' : 'Passwort *' }}</label>
            <input v-model="editing.password" type="password" />
            <small class="hint">Mindestens 8 Zeichen</small>
          </div>

          <div class="form-row">
            <label>Aktiv</label>
            <label class="check-row">
              <input type="checkbox" v-model="editing.active" />
              Benutzer kann sich anmelden
            </label>
          </div>

          <fieldset class="fset">
            <legend>Rollen</legend>
            <div class="check-grid">
              <label v-for="r in catalog.roles" :key="r.value" class="check-row">
                <input type="checkbox" :value="r.value"
                       :checked="editing.roles.includes(r.value)"
                       @change="toggle(editing.roles, r.value, $event)" />
                <code>{{ r.value }}</code>
                <span class="muted small">{{ r.permissions.length }} Permissions</span>
              </label>
            </div>
            <p class="hint">Rollen vergeben Permissions. Mehrere Rollen sind additiv.</p>
          </fieldset>

          <fieldset class="fset">
            <legend>Sichtbare Module (Whitelist)</legend>
            <label class="check-row">
              <input type="checkbox" :checked="editing.allowed_modules === null"
                     @change="onAllModulesToggle($event)" />
              <strong>Alle Module aus Rolle automatisch freischalten</strong>
            </label>
            <div v-if="editing.allowed_modules !== null" class="check-grid mt-1">
              <label v-for="m in catalog.modules" :key="m.id" class="check-row">
                <input type="checkbox" :value="m.id"
                       :checked="(editing.allowed_modules || []).includes(m.id)"
                       @change="toggle(editing.allowed_modules, m.id, $event)" />
                <strong>{{ m.label }}</strong>
              </label>
            </div>
            <p class="hint">Whitelist überschreibt die Modul-Auswahl aus Rollen — nützlich, wenn ein Admin nur bestimmte Module sehen soll.</p>
          </fieldset>

          <fieldset class="fset">
            <legend>Zusätzliche Permissions (additiv zu Rollen)</legend>
            <div v-for="m in catalog.modules" :key="m.id" class="perm-group">
              <strong>{{ m.label }}</strong>
              <div class="check-row-inline">
                <label v-for="p in m.permissions" :key="p.value" class="check-row">
                  <input type="checkbox" :value="p.value"
                         :checked="editing.extra_permissions.includes(p.value)"
                         @change="toggle(editing.extra_permissions, p.value, $event)" />
                  <code>{{ p.label }}</code>
                </label>
              </div>
            </div>
            <div class="perm-group">
              <strong>Administration</strong>
              <div class="check-row-inline">
                <label v-for="p in catalog.admin_permissions" :key="p.value" class="check-row">
                  <input type="checkbox" :value="p.value"
                         :checked="editing.extra_permissions.includes(p.value)"
                         @change="toggle(editing.extra_permissions, p.value, $event)" />
                  <code>{{ p.label }}</code>
                </label>
              </div>
            </div>
          </fieldset>

          <details v-if="editing.id" class="effective-perms">
            <summary>Effektive Permissions (Rollen + extra)</summary>
            <div class="effective-list">
              <code v-for="p in computeEffective(editing)" :key="p">{{ p }}</code>
            </div>
          </details>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="editing = null">Abbrechen</button>
          <button class="btn-primary" @click="onSave" :disabled="!canSave">Speichern</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import apiClient from '../../api/client'

interface User {
  id: string
  email: string
  display_name: string
  roles: string[]
  allowed_modules: string[] | null
  extra_permissions: string[]
  effective_permissions: string[]
  effective_modules: string[]
  active: boolean
  created_at?: string
  updated_at?: string
  last_login?: string | null
}

interface CatalogModule {
  id: string
  label: string
  permissions: { value: string; label: string }[]
}
interface CatalogRole {
  value: string
  permissions: string[]
}
interface Catalog {
  modules: CatalogModule[]
  roles: CatalogRole[]
  admin_permissions: { value: string; label: string }[]
}

const users = ref<User[]>([])
const loading = ref(false)
const error = ref('')
const catalog = reactive<Catalog>({ modules: [], roles: [], admin_permissions: [] })

interface EditState {
  id: string
  email: string
  display_name: string
  roles: string[]
  allowed_modules: string[] | null
  extra_permissions: string[]
  active: boolean
  password?: string
}
const editing = ref<EditState | null>(null)

const canSave = computed(() => {
  if (!editing.value) return false
  if (!editing.value.email) return false
  if (!editing.value.id && !editing.value.password) return false
  return true
})

const reload = async () => {
  loading.value = true
  try {
    const [u, c] = await Promise.all([
      apiClient.get('/admin/users'),
      apiClient.get('/admin/permissions/catalog'),
    ])
    users.value = u.data
    Object.assign(catalog, c.data)
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Fehler beim Laden'
  } finally {
    loading.value = false
  }
}

const formatDate = (s?: string | null): string => {
  if (!s) return '—'
  try { return new Date(s).toLocaleString('de-DE') } catch { return s }
}

const startNew = () => {
  editing.value = {
    id: '',
    email: '',
    display_name: '',
    roles: [],
    allowed_modules: null,
    extra_permissions: [],
    active: true,
    password: '',
  }
}

const openEdit = (u: User) => {
  editing.value = {
    id: u.id,
    email: u.email,
    display_name: u.display_name || '',
    roles: [...(u.roles || [])],
    allowed_modules: u.allowed_modules === null ? null : [...(u.allowed_modules || [])],
    extra_permissions: [...(u.extra_permissions || [])],
    active: u.active,
    password: '',
  }
}

const toggle = (list: string[] | null, value: string, e: Event) => {
  if (list === null) return
  const checked = (e.target as HTMLInputElement).checked
  if (checked && !list.includes(value)) list.push(value)
  else if (!checked) {
    const i = list.indexOf(value)
    if (i >= 0) list.splice(i, 1)
  }
}

const onAllModulesToggle = (e: Event) => {
  if (!editing.value) return
  const checked = (e.target as HTMLInputElement).checked
  editing.value.allowed_modules = checked ? null : []
}

const computeEffective = (u: EditState): string[] => {
  const set = new Set<string>()
  for (const r of u.roles) {
    const role = catalog.roles.find(x => x.value === r)
    if (role) role.permissions.forEach(p => set.add(p))
  }
  for (const p of u.extra_permissions) set.add(p)
  return Array.from(set).sort()
}

const onSave = async () => {
  if (!editing.value) return
  const e = editing.value
  const payload: any = {
    email: e.email,
    display_name: e.display_name,
    roles: e.roles,
    allowed_modules: e.allowed_modules,
    extra_permissions: e.extra_permissions,
    active: e.active,
  }
  if (e.password) payload.password = e.password

  try {
    if (e.id) {
      await apiClient.put(`/admin/users/${e.id}`, payload)
    } else {
      await apiClient.post('/admin/users', payload)
    }
    editing.value = null
    await reload()
  } catch (err: any) {
    error.value = err?.response?.data?.error || 'Speichern fehlgeschlagen'
  }
}

const onDelete = async (u: User) => {
  if (!confirm(`Benutzer "${u.email}" wirklich löschen?`)) return
  try {
    await apiClient.delete(`/admin/users/${u.id}`)
    await reload()
  } catch (err: any) {
    error.value = err?.response?.data?.error || 'Löschen fehlgeschlagen'
  }
}

onMounted(reload)
</script>

<style scoped>
.users-view { max-width: 1400px; padding: 16px; }

.header { display: flex; align-items: flex-end; gap: 16px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border); }
.header h2 { margin: 0; flex: 0; }
.header p { flex: 1; margin: 0; color: var(--color-text-secondary); font-size: 13px; }

.alert-error {
  background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px;
  margin-bottom: 12px; border: 1px solid #ef5350; cursor: pointer;
}

.empty, .loading { padding: 32px; text-align: center; color: var(--color-text-secondary); }

.users-table { width: 100%; border-collapse: collapse; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden; }
.users-table th { background: var(--color-background); text-align: left; padding: 10px 12px; font-size: 12px; font-weight: 600; border-bottom: 1px solid var(--color-border); }
.users-table td { padding: 10px 12px; border-bottom: 1px solid var(--color-border); font-size: 13px; vertical-align: top; }
.users-table tr:hover { background: var(--color-background); }

.role-tag, .mod-tag {
  display: inline-block; font-family: monospace; font-size: 11px;
  padding: 2px 8px; border-radius: 3px; margin: 2px;
}
.role-tag { background: #e3f2fd; color: #1565c0; }
.mod-tag { background: #f3e5f5; color: #6a1b9a; }
.muted { color: var(--color-text-secondary); }
.small { font-size: 12px; }

.status { padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.status.on { background: #e8f5e9; color: #2e7d32; }
.status.off { background: #ffebee; color: #c62828; }

.btn-icon { background: none; border: none; cursor: pointer; padding: 4px 6px; font-size: 14px; }
.btn-icon:hover { background: var(--color-background); border-radius: 4px; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: var(--color-surface); border-radius: 8px; max-width: 600px; width: 90%; max-height: 92vh; display: flex; flex-direction: column; }
.modal-wide { max-width: 850px; }
.modal-header { background: var(--color-primary); color: #fff; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; }
.modal-header h3 { margin: 0; font-size: 16px; }
.btn-close { background: none; border: none; color: #fff; font-size: 22px; cursor: pointer; }
.modal-body { padding: 20px; overflow-y: auto; flex: 1; }
.modal-footer { padding: 12px 20px; border-top: 1px solid var(--color-border); display: flex; gap: 8px; justify-content: flex-end; }

.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px;
  background: var(--color-surface); color: var(--color-text-primary);
}
.form-row input:disabled { background: var(--color-background); }
.hint { font-size: 11px; color: var(--color-text-secondary); }

.check-row { display: flex; align-items: center; gap: 6px; padding: 4px 0; cursor: pointer; font-size: 13px; }
.check-row input[type=checkbox] { margin: 0; }
.check-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 4px; }
.check-row-inline { display: flex; flex-wrap: wrap; gap: 12px; padding: 4px 0; }

.fset {
  border: 1px solid var(--color-border); border-radius: 6px;
  padding: 12px 16px; margin: 16px 0;
}
.fset legend { font-weight: 600; padding: 0 6px; }

.perm-group { padding: 6px 0; border-bottom: 1px solid var(--color-background); }
.perm-group:last-child { border-bottom: none; }
.perm-group strong { display: block; margin-bottom: 4px; font-size: 12px; color: var(--color-text-secondary); }

.effective-perms { background: var(--color-background); padding: 10px; border-radius: 4px; margin-top: 12px; }
.effective-perms summary { cursor: pointer; font-weight: 600; font-size: 13px; }
.effective-list { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
.effective-list code { background: var(--color-surface); padding: 2px 6px; border-radius: 3px; font-size: 11px; }

.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-primary:hover:not(:disabled) { background: var(--color-primary-dark); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: var(--color-background); color: var(--color-primary); border: 1px solid var(--color-border); padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-secondary:hover { background: var(--color-border); }

.mt-1 { margin-top: 8px; }
</style>
