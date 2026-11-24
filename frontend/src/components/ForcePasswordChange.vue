<!-- #2105: Erzwungene Kennwortänderung bei nächster Anmeldung.
     Blockierender Vollbild-Dialog — kein Abbrechen, bis das Kennwort geändert
     ist. Bewusst NICHT über ModalRahmen (der schließt bei Escape/Hintergrund);
     dieser Dialog darf nicht geschlossen werden. -->
<template>
  <div class="fpc-overlay" role="dialog" aria-modal="true" aria-labelledby="fpc-titel">
    <div class="fpc-card">
      <h2 id="fpc-titel">🔐 Kennwort ändern</h2>
      <p class="fpc-hinweis">
        Ihr Kennwort wurde von einer Administratorin oder einem Administrator
        gesetzt. Bitte vergeben Sie jetzt ein eigenes Kennwort, um fortzufahren.
      </p>
      <form @submit.prevent="absenden">
        <label class="fpc-label">Aktuelles (Start-)Kennwort
          <input v-model="altesKw" type="password" autocomplete="current-password"
                 required :disabled="laeuft" />
        </label>
        <label class="fpc-label">Neues Kennwort
          <input v-model="neuesKw" type="password" autocomplete="new-password"
                 required :disabled="laeuft" />
        </label>
        <label class="fpc-label">Neues Kennwort bestätigen
          <input v-model="neuesKw2" type="password" autocomplete="new-password"
                 required :disabled="laeuft" />
        </label>
        <p v-if="fehler" class="fpc-fehler" role="alert">{{ fehler }}</p>
        <button type="submit" class="fpc-btn" :disabled="laeuft || !gueltig">
          {{ laeuft ? 'Wird gespeichert…' : 'Kennwort ändern' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import { fehlerText } from '../utils/fehler'

const authStore = useAuthStore()
const altesKw = ref('')
const neuesKw = ref('')
const neuesKw2 = ref('')
const fehler = ref('')
const laeuft = ref(false)

const gueltig = computed(() =>
  !!altesKw.value && !!neuesKw.value && neuesKw.value === neuesKw2.value)

const absenden = async () => {
  fehler.value = ''
  if (neuesKw.value !== neuesKw2.value) {
    fehler.value = 'Die beiden neuen Kennwörter stimmen nicht überein.'
    return
  }
  laeuft.value = true
  try {
    await authStore.changePassword(altesKw.value, neuesKw.value)
    // Erfolg: mustChangePassword ist jetzt false → der Dialog verschwindet.
  } catch (e: any) {
    fehler.value = fehlerText(e) || 'Kennwortänderung fehlgeschlagen.'
  } finally {
    laeuft.value = false
  }
}
</script>

<style scoped>
.fpc-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3000;
  padding: 16px;
}
.fpc-card {
  background: var(--card-bg, #fff);
  color: var(--text, #17181d);
  border-radius: 12px;
  padding: 28px;
  width: 100%;
  max-width: 420px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35);
}
.fpc-card h2 { margin: 0 0 12px; font-size: 1.25rem; }
.fpc-hinweis { margin: 0 0 18px; color: var(--text-muted, #475569); font-size: 0.92rem; }
.fpc-label { display: block; margin-bottom: 14px; font-size: 0.88rem; font-weight: 600; }
.fpc-label input {
  display: block; width: 100%; margin-top: 6px; padding: 9px 11px;
  border: 1px solid var(--border, #cbd5e1); border-radius: 8px;
  font-size: 0.95rem; box-sizing: border-box;
}
.fpc-fehler { color: #b91c1c; font-size: 0.88rem; margin: 6px 0 12px; }
.fpc-btn {
  width: 100%; padding: 11px; border: none; border-radius: 8px;
  background: var(--marke, #fd5a21); color: #fff; font-weight: 700;
  font-size: 0.98rem; cursor: pointer;
}
.fpc-btn:disabled { opacity: 0.55; cursor: not-allowed; }
</style>
