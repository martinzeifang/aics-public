<template>
  <div class="forgot-wrap">
    <div class="card">
      <h2>🔑 Passwort vergessen</h2>
      <p class="muted">
        Gib deine E-Mail-Adresse ein. Falls ein Konto existiert, senden wir dir einen
        einmaligen Link zum Zurücksetzen deines Passworts.
      </p>

      <form @submit.prevent="submit" v-if="!done">
        <label>
          E-Mail
          <input v-model="email" type="email" autocomplete="email" required />
        </label>
        <button class="btn-primary" :disabled="loading">
          {{ loading ? 'Sende…' : 'Reset-Link anfordern' }}
        </button>
      </form>

      <div v-if="done" class="ok">
        ✓ {{ message }}
        <div v-if="resetUrl" class="dev-hint">
          <small>DEV-Modus:</small> <router-link :to="resetUrl">{{ resetUrl }}</router-link>
        </div>
      </div>

      <div v-if="error" class="fail">⚠ {{ error }}</div>

      <p style="margin-top: 16px;">
        <router-link to="/login">← Zurück zum Login</router-link>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'

const email = ref('')
const loading = ref(false)
const done = ref(false)
const message = ref('')
const resetUrl = ref('')
const error = ref('')

async function submit() {
  loading.value = true
  error.value = ''
  try {
    const r = await axios.post('/api/auth/password/forgot', { email: email.value })
    done.value = true
    message.value = r.data?.message || 'Falls die E-Mail existiert, wurde ein Link gesendet.'
    resetUrl.value = r.data?.reset_url || ''
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Fehler beim Anfordern.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.forgot-wrap { display: flex; justify-content: center; padding: 60px 20px; }
.card { max-width: 480px; background: var(--color-surface, #fff); padding: 32px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.muted { color: var(--color-text-muted, #666); margin-bottom: 16px; }
label { display: block; margin-bottom: 12px; }
label input { display: block; width: 100%; padding: 8px; margin-top: 4px; box-sizing: border-box; }
.btn-primary { background: var(--color-primary, #1565c0); color: #fff; border: 0; padding: 10px 18px; border-radius: 6px; cursor: pointer; }
.btn-primary:disabled { opacity: 0.6; cursor: wait; }
.ok { color: #2e7d32; margin-top: 12px; }
.fail { color: #c62828; margin-top: 12px; }
.dev-hint { margin-top: 8px; padding: 8px; background: #fff8e1; border-radius: 4px; font-family: monospace; font-size: 12px; }
</style>
