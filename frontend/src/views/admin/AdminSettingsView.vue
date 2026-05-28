<template>
  <div class="admin-settings">
    <header class="page-header">
      <h1>⚙️ Einstellungen</h1>
      <p class="muted">
        KI-Provider, GitHub-Integration, Module, Backup, Erscheinungsbild —
        alles an einem Ort. Änderungen werden persistent im Server-Volume gespeichert.
      </p>
    </header>

    <!-- Sprint ε Phase D — MFA-Policy -->
    <section class="mfa-policy-card">
      <h2>🔐 MFA-Richtlinie</h2>
      <p class="muted">
        Mehr-Faktor-Authentifizierung (TOTP oder Passkey) ist für alle Benutzer verfügbar.
        Hier legen Sie fest, ob sie verpflichtend ist.
      </p>

      <div v-if="mfaLoading" class="muted">Lade Richtlinie…</div>
      <template v-else>
        <div class="form-row">
          <label>Modus</label>
          <select v-model="mfaPolicy.mode">
            <option value="optional">Optional — jeder kann MFA selbst aktivieren</option>
            <option value="required_all">Pflicht für alle Benutzer</option>
            <option value="required_roles">Pflicht für bestimmte Rollen</option>
          </select>
        </div>

        <div v-if="mfaPolicy.mode === 'required_roles'" class="form-row">
          <label>Betroffene Rollen</label>
          <div class="role-checks">
            <label v-for="r in knownRoles" :key="r" class="role-check">
              <input type="checkbox" :value="r"
                     :checked="mfaPolicy.required_roles.includes(r)"
                     @change="toggleRole(r, $event)" />
              {{ r }}
            </label>
          </div>
        </div>

        <div v-if="mfaPolicy.mode !== 'optional'" class="form-row">
          <label>Übergangsfrist (Tage bis Einrichtung erzwungen wird)</label>
          <input type="number" min="0" max="90" v-model.number="mfaPolicy.grace_days" />
        </div>

        <div class="btn-row">
          <button class="btn-primary" @click="saveMfaPolicy" :disabled="mfaSaving">
            {{ mfaSaving ? 'Speichert…' : 'Richtlinie speichern' }}
          </button>
          <span v-if="mfaSavedMsg" class="ok">{{ mfaSavedMsg }}</span>
          <span v-if="mfaError" class="err">⚠ {{ mfaError }}</span>
        </div>
      </template>
    </section>

    <SettingsDialog :open="true" :embedded="true" @close="onClose" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import SettingsDialog from '../../components/SettingsDialog.vue'

const router = useRouter()
function onClose() {
  router.push('/admin')
}

// ── MFA-Policy (Sprint ε Phase D) ──────────────────────────────
interface MfaPolicy { mode: string; required_roles: string[]; grace_days: number }
const knownRoles = ['admin', 'cra_editor', 'cra_viewer', 'auditor', 'manager']
const mfaPolicy = ref<MfaPolicy>({ mode: 'optional', required_roles: [], grace_days: 7 })
const mfaLoading = ref(true)
const mfaSaving = ref(false)
const mfaSavedMsg = ref('')
const mfaError = ref('')

const toggleRole = (role: string, e: Event) => {
  const checked = (e.target as HTMLInputElement).checked
  const list = mfaPolicy.value.required_roles
  if (checked && !list.includes(role)) list.push(role)
  else if (!checked) mfaPolicy.value.required_roles = list.filter(r => r !== role)
}

const loadMfaPolicy = async () => {
  mfaLoading.value = true
  try {
    const r = await axios.get('/api/admin/mfa-policy')
    mfaPolicy.value = {
      mode: r.data.mode || 'optional',
      required_roles: r.data.required_roles || [],
      grace_days: r.data.grace_days ?? 7,
    }
  } catch (e: any) {
    mfaError.value = e?.response?.data?.error || 'Richtlinie konnte nicht geladen werden'
  } finally {
    mfaLoading.value = false
  }
}

const saveMfaPolicy = async () => {
  mfaSaving.value = true
  mfaError.value = ''
  mfaSavedMsg.value = ''
  try {
    await axios.put('/api/admin/mfa-policy', mfaPolicy.value)
    mfaSavedMsg.value = '✓ Gespeichert'
    setTimeout(() => { mfaSavedMsg.value = '' }, 3000)
  } catch (e: any) {
    mfaError.value = e?.response?.data?.error || 'Speichern fehlgeschlagen'
  } finally {
    mfaSaving.value = false
  }
}

onMounted(loadMfaPolicy)
</script>

<style scoped>
.admin-settings { max-width: 1200px; padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { margin: 0 0 4px; }
.muted { color: var(--color-text-muted, #666); margin: 0 0 12px; }

.mfa-policy-card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 10px;
  padding: 20px 24px;
  margin-bottom: 24px;
}
.mfa-policy-card h2 { margin: 0 0 6px; font-size: 18px; }
.form-row { margin-bottom: 14px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row select, .form-row input[type="number"] {
  padding: 8px 10px; border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px; font-size: 14px; min-width: 280px;
}
.role-checks { display: flex; flex-wrap: wrap; gap: 12px; }
.role-check { display: inline-flex; align-items: center; gap: 6px; font-weight: 400; font-size: 13px; }
.btn-row { display: flex; align-items: center; gap: 12px; margin-top: 8px; }
.btn-primary {
  padding: 10px 16px; background: #1565c0; color: #fff; border: none;
  border-radius: 8px; font-size: 14px; cursor: pointer;
}
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.ok { color: #2e7d32; font-size: 13px; }
.err { color: #c62828; font-size: 13px; }
</style>
