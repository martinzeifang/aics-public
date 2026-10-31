<!--
  Gruppenverwaltung (#1779).

  Die Gruppe ist die Stelle, an der eine Rechte-Entscheidung einmal steht.
  Zwei Dinge macht diese Seite deshalb ausdrücklich sichtbar:

  * **Was eine Gruppe wirklich gibt** — die Rollen eines Moduls sind Bündel;
    wer sie vergibt, soll die darin enthaltenen Berechtigungen sehen.
  * **Dass eine Rechteänderung abmeldet** — Berechtigungen stehen im Token.
    Wird die Gruppe geändert, fallen die Tokens der Mitglieder, und sie müssen
    sich neu anmelden. Das steht hier als Hinweis, nicht als Überraschung.
-->
<template>
  <div class="groups-view">
    <div class="header">
      <h2>👪 Gruppen</h2>
      <p>Berechtigungen einmal vergeben und Benutzer zuordnen</p>
      <button class="btn-secondary" @click="oeffneVorschlaege">📋 Standardgruppen anlegen…</button>
      <button class="btn-primary" @click="neu">+ Neue Gruppe</button>
    </div>

    <FehlerHinweis :text="fehler" @close="fehler = ''" />
    <div v-if="hinweis" class="alert alert-info" @click="hinweis = ''">{{ hinweis }}</div>

    <table v-if="gruppen.length" class="data-table">
      <thead>
        <tr>
          <th>Name</th><th>Beschreibung</th><th>Rollen</th>
          <th>Einzelrechte</th><th>Mitglieder</th><th>Status</th><th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="g in gruppen" :key="g.id">
          <td><strong>{{ g.name }}</strong></td>
          <td class="small">{{ g.beschreibung || '—' }}</td>
          <td>
            <span v-for="r in g.roles" :key="r" class="tag">{{ r }}</span>
            <span v-if="!g.roles.length" class="muted">—</span>
          </td>
          <td class="small">{{ g.extra_permissions.length || '—' }}</td>
          <td>{{ g.mitglieder_count ?? 0 }}</td>
          <td>
            <span :class="['status', g.active ? 'on' : 'off']">
              {{ g.active ? 'Aktiv' : 'Stillgelegt' }}
            </span>
          </td>
          <td class="actions">
            <button class="btn-icon" title="Bearbeiten" @click="oeffnen(g)">✏️</button>
            <button class="btn-icon" title="Mitglieder" @click="oeffnenMitglieder(g)">👥</button>
            <button class="btn-icon" title="Löschen" @click="loeschen(g)">🗑️</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else-if="!laden_" class="empty">
      Noch keine Gruppen. Eine Gruppe bündelt Rollen und Einzelrechte und gibt sie
      an alle Mitglieder weiter.
    </div>
    <div v-if="laden_" class="loading">Lade Gruppen…</div>

    <!-- #1780: Vorschläge, keine Vorbelegung. Angelegt wird nur das Angehakte;
         vorhandene Gruppen werden übersprungen, nie überschrieben. -->
    <div v-if="vorschlaegeOffen" class="modal-overlay" @mousedown.self="vorschlaegeOffen = false">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>Standardgruppen anlegen</h3>
          <button class="btn-close" @click="vorschlaegeOffen = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">
            Zuschnitte, die sich in der Praxis wiederholen. Angelegt wird nur, was Sie
            auswählen — danach sind es gewöhnliche Gruppen und frei änderbar. Gruppen,
            die es schon gibt, bleiben unberührt.
          </p>
          <div v-for="v in vorschlaege" :key="v.key" class="v-karte">
            <label class="check-row">
              <input type="checkbox" :value="v.key" v-model="vorschlagAuswahl"
                     :disabled="v.vorhanden" />
              <strong>{{ v.name }}</strong>
              <span v-if="v.vorhanden" class="muted small">— existiert bereits</span>
              <span v-else class="muted small">{{ v.permissions_count }} Berechtigungen</span>
            </label>
            <p class="v-text">{{ v.beschreibung }}</p>
            <p class="v-rollen">
              <span v-for="r in v.roles" :key="r" class="tag">{{ r }}</span>
            </p>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="vorschlaegeOffen = false">Abbrechen</button>
          <button class="btn-primary" :disabled="!vorschlagAuswahl.length || speichert"
                  @click="legeVorschlaegeAn">
            {{ speichert ? 'Lege an…' : `${vorschlagAuswahl.length} Gruppe(n) anlegen` }}
          </button>
        </div>
      </div>
    </div>

    <!-- Bearbeiten / Neu -->
    <div v-if="form" class="modal-overlay" @mousedown.self="form = null">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>{{ form.id ? 'Gruppe bearbeiten' : 'Neue Gruppe' }}</h3>
          <button class="btn-close" @click="form = null">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Name *</label>
            <input v-model="form.name" placeholder="z.B. CRA-Bearbeitung" />
          </div>
          <div class="form-row">
            <label>Beschreibung</label>
            <input v-model="form.beschreibung" placeholder="Wofür ist diese Gruppe?" />
          </div>
          <div class="form-row">
            <label>Aktiv</label>
            <label class="check-row">
              <input type="checkbox" v-model="form.active" />
              Rechte dieser Gruppe wirken
            </label>
          </div>

          <fieldset class="fset">
            <legend>Rollen</legend>
            <p class="hint">
              Eine Rolle ist ein Bündel von Berechtigungen. Die Liste unter der
              Auswahl zeigt, was tatsächlich dazugehört.
            </p>
            <div class="rollen">
              <label v-for="r in katalog.roles" :key="r.value" class="check-row">
                <input type="checkbox" :value="r.value" v-model="form.roles" />
                {{ r.value }}
                <span class="muted small">({{ r.permissions.length }} Rechte)</span>
              </label>
            </div>
          </fieldset>

          <fieldset class="fset">
            <legend>Einzelne Berechtigungen (zusätzlich)</legend>
            <div v-for="m in katalog.modules" :key="m.id" class="perm-group">
              <div class="perm-head">{{ m.label }}</div>
              <label v-for="p in m.permissions" :key="p.value" class="check-row inline">
                <input type="checkbox" :value="p.value" v-model="form.extra_permissions" />
                {{ p.label }}
              </label>
            </div>
            <div class="perm-group">
              <div class="perm-head">Administration</div>
              <label v-for="p in katalog.admin_permissions" :key="p.value" class="check-row inline">
                <input type="checkbox" :value="p.value" v-model="form.extra_permissions" />
                {{ p.label }}
              </label>
            </div>
          </fieldset>

          <div class="wirkung">
            <strong>Effektive Berechtigungen:</strong> {{ effektiv.length }}
            <details v-if="effektiv.length">
              <summary>anzeigen</summary>
              <code>{{ effektiv.join(', ') }}</code>
            </details>
          </div>
          <p class="warn">
            ⚠️ Eine Rechteänderung meldet alle Mitglieder ab — Berechtigungen stehen
            im Anmelde-Token. Sie müssen sich danach neu anmelden; genau so wirkt ein
            entzogenes Recht sofort.
          </p>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="form = null">Abbrechen</button>
          <button class="btn-primary" :disabled="!form.name.trim() || speichert"
                  @click="speichern">
            {{ speichert ? 'Speichere…' : 'Speichern' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Mitglieder -->
    <div v-if="mitglieder" class="modal-overlay" @mousedown.self="mitglieder = null">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Mitglieder — {{ mitglieder.name }}</h3>
          <button class="btn-close" @click="mitglieder = null">✕</button>
        </div>
        <div class="modal-body">
          <ul v-if="mitglieder.mitglieder?.length" class="mitglieder">
            <li v-for="uid in mitglieder.mitglieder" :key="uid">
              {{ benutzerLabel(uid) }}
              <button class="btn-link" @click="entfernen(uid)">entfernen</button>
            </li>
          </ul>
          <p v-else class="muted">Niemand in dieser Gruppe.</p>

          <div class="form-row">
            <label>Benutzer hinzufügen</label>
            <select v-model="neuesMitglied">
              <option value="">— auswählen —</option>
              <option v-for="u in nichtMitglieder" :key="u.id" :value="u.id">
                {{ u.email }}{{ u.display_name ? ` · ${u.display_name}` : '' }}
              </option>
            </select>
            <button class="btn-secondary" :disabled="!neuesMitglied" @click="hinzufuegen">
              Hinzufügen
            </button>
          </div>
          <p class="warn">
            ⚠️ Auch das Zuordnen und Entfernen meldet das betroffene Konto ab.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import apiClient from '../../api/client'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'

interface Gruppe {
  id: number
  name: string
  beschreibung: string
  roles: string[]
  extra_permissions: string[]
  active: boolean
  mitglieder?: string[]
  mitglieder_count?: number
}
interface Benutzer { id: string; email: string; display_name?: string }
interface Katalog {
  modules: Array<{ id: string; label: string; permissions: Array<{ value: string; label: string }> }>
  roles: Array<{ value: string; permissions: string[] }>
  admin_permissions: Array<{ value: string; label: string }>
}

const gruppen = ref<Gruppe[]>([])
const benutzer = ref<Benutzer[]>([])
const katalog = reactive<Katalog>({ modules: [], roles: [], admin_permissions: [] })
const laden_ = ref(false)
const fehler = ref('')
const hinweis = ref('')
const speichert = ref(false)

interface GruppenVorschlag {
  key: string; name: string; beschreibung: string; roles: string[]
  permissions_count: number; vorhanden: boolean
}
const vorschlaege = ref<GruppenVorschlag[]>([])
const vorschlaegeOffen = ref(false)
const vorschlagAuswahl = ref<string[]>([])

const form = ref<Gruppe | null>(null)
const mitglieder = ref<Gruppe | null>(null)
const neuesMitglied = ref('')

/** Was die Auswahl zusammen ergibt — gerechnet wie im Backend (additiv). */
const effektiv = computed(() => {
  if (!form.value) return []
  const menge = new Set<string>(form.value.extra_permissions)
  for (const r of form.value.roles) {
    for (const p of katalog.roles.find(x => x.value === r)?.permissions || []) menge.add(p)
  }
  return [...menge].sort()
})

const nichtMitglieder = computed(() => {
  const drin = new Set(mitglieder.value?.mitglieder || [])
  return benutzer.value.filter(u => !drin.has(u.id))
})

function benutzerLabel(uid: string): string {
  const u = benutzer.value.find(x => x.id === uid)
  return u ? `${u.email}${u.display_name ? ` · ${u.display_name}` : ''}` : uid
}

async function laden() {
  laden_.value = true
  fehler.value = ''
  try {
    const [g, u, k] = await Promise.all([
      apiClient.get('/admin/groups'),
      apiClient.get('/admin/users'),
      apiClient.get('/admin/permissions/catalog'),
    ])
    gruppen.value = g.data || []
    benutzer.value = u.data || []
    Object.assign(katalog, k.data || {})
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Gruppen konnten nicht geladen werden'
  } finally {
    laden_.value = false
  }
}

async function oeffneVorschlaege() {
  fehler.value = ''
  try {
    const res = await apiClient.get('/admin/groups/vorschlaege')
    vorschlaege.value = res.data || []
    vorschlagAuswahl.value = vorschlaege.value.filter(v => !v.vorhanden).map(v => v.key)
    vorschlaegeOffen.value = true
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Vorschläge nicht ladbar'
  }
}

async function legeVorschlaegeAn() {
  speichert.value = true
  fehler.value = ''
  try {
    const res = await apiClient.post('/admin/groups/vorschlaege',
                                     { keys: vorschlagAuswahl.value })
    const n = (res.data?.angelegt || []).length
    const u = (res.data?.uebersprungen || []).length
    hinweis.value = `${n} Gruppe(n) angelegt`
      + (u ? `, ${u} bereits vorhanden und unverändert gelassen.` : '.')
    vorschlaegeOffen.value = false
    await laden()
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Anlegen fehlgeschlagen'
  } finally {
    speichert.value = false
  }
}

function neu() {
  form.value = { id: 0, name: '', beschreibung: '', roles: [], extra_permissions: [],
                 active: true }
}

function oeffnen(g: Gruppe) {
  form.value = { ...g, roles: [...g.roles], extra_permissions: [...g.extra_permissions] }
}

async function oeffnenMitglieder(g: Gruppe) {
  try {
    const res = await apiClient.get(`/admin/groups/${g.id}`)
    mitglieder.value = res.data
    neuesMitglied.value = ''
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Mitglieder nicht ladbar'
  }
}

async function speichern() {
  if (!form.value) return
  speichert.value = true
  fehler.value = ''
  try {
    const body = {
      name: form.value.name.trim(),
      beschreibung: form.value.beschreibung,
      roles: form.value.roles,
      extra_permissions: form.value.extra_permissions,
      active: form.value.active,
    }
    const res = form.value.id
      ? await apiClient.put(`/admin/groups/${form.value.id}`, body)
      : await apiClient.post('/admin/groups', body)
    const abgemeldet = res.data?.abgemeldete_mitglieder || 0
    hinweis.value = abgemeldet
      ? `Gespeichert. ${abgemeldet} Mitglied(er) müssen sich neu anmelden.`
      : 'Gespeichert.'
    form.value = null
    await laden()
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Speichern fehlgeschlagen'
  } finally {
    speichert.value = false
  }
}

async function loeschen(g: Gruppe) {
  if (!window.confirm(`Gruppe „${g.name}" löschen? Die Konten bleiben bestehen, `
      + 'verlieren aber die Rechte dieser Gruppe.')) return
  try {
    const res = await apiClient.delete(`/admin/groups/${g.id}`)
    hinweis.value = `Gruppe gelöscht. ${res.data?.abgemeldete_mitglieder || 0} `
      + 'Mitglied(er) müssen sich neu anmelden.'
    await laden()
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Löschen fehlgeschlagen'
  }
}

async function hinzufuegen() {
  if (!mitglieder.value || !neuesMitglied.value) return
  try {
    const res = await apiClient.post(`/admin/groups/${mitglieder.value.id}/members`,
                                     { user_id: neuesMitglied.value })
    mitglieder.value = res.data
    neuesMitglied.value = ''
    await laden()
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Hinzufügen fehlgeschlagen'
  }
}

async function entfernen(uid: string) {
  if (!mitglieder.value) return
  try {
    const res = await apiClient.delete(
      `/admin/groups/${mitglieder.value.id}/members/${encodeURIComponent(uid)}`)
    mitglieder.value = res.data
    await laden()
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Entfernen fehlgeschlagen'
  }
}

onMounted(laden)
</script>

<style scoped>
.groups-view { max-width: 1300px; padding: 16px; }
.header { display: flex; align-items: flex-end; gap: 16px; margin-bottom: 16px;
  padding-bottom: 12px; border-bottom: 1px solid var(--color-border); }
.header h2 { margin: 0; }
.header p { flex: 1; margin: 0; color: var(--color-text-secondary); font-size: 13px; }

.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { text-align: left; padding: 8px 10px;
  border-bottom: 1px solid var(--color-border); font-size: 13px; vertical-align: top; }
.small { font-size: 12px; }
.muted { color: var(--color-text-secondary); }
.tag { display: inline-block; background: #e3f2fd; color: #1565c0; border-radius: 10px;
  padding: 2px 8px; font-size: 11px; margin: 0 4px 4px 0; }
.status.on { color: #2e7d32; }
.status.off { color: #b71c1c; }
.actions { white-space: nowrap; }
.btn-icon { background: none; border: none; cursor: pointer; font-size: 15px; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer;
  font-size: 12px; margin-left: 8px; }
.empty, .loading { padding: 20px; color: var(--color-text-secondary); font-size: 13px; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, .45);
  display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: var(--color-bg, #fff); border-radius: 10px; width: 560px;
  max-width: 94vw; max-height: 90vh; display: flex; flex-direction: column; }
.modal-wide { width: 860px; }
.modal-header, .modal-footer { display: flex; align-items: center; gap: 12px;
  padding: 12px 16px; border-bottom: 1px solid var(--color-border); }
.modal-footer { border-bottom: none; border-top: 1px solid var(--color-border);
  justify-content: flex-end; }
.modal-header h3 { margin: 0; flex: 1; font-size: 16px; }
.modal-body { padding: 14px 16px; overflow: auto; }
.btn-close { background: none; border: none; font-size: 16px; cursor: pointer; }

.form-row { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.form-row label { font-size: 12px; font-weight: 600; }
.form-row input[type="text"], .form-row input:not([type]), .form-row select {
  padding: 6px 8px; border: 1px solid var(--color-border); border-radius: 6px; }
.check-row { display: flex; align-items: center; gap: 6px; font-weight: 400;
  font-size: 13px; }
.check-row.inline { display: inline-flex; margin-right: 14px; }
.fset { border: 1px solid var(--color-border); border-radius: 8px; padding: 10px 12px;
  margin-bottom: 12px; }
.fset legend { font-size: 13px; font-weight: 600; padding: 0 6px; }
.hint { font-size: 12px; color: var(--color-text-secondary); margin: 0 0 8px; }
.rollen { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 4px; }
.perm-group { margin-bottom: 8px; }
.perm-head { font-size: 12px; font-weight: 600; margin-bottom: 2px; }
.v-karte { border: 1px solid var(--color-border); border-radius: 8px; padding: 10px 12px;
  margin-bottom: 10px; }
.v-text { font-size: 12px; color: var(--color-text-secondary); margin: 4px 0; }
.v-rollen { margin: 0; }
.wirkung { font-size: 13px; background: #f1f8e9; border: 1px solid #c5e1a5;
  border-radius: 6px; padding: 8px 10px; }
.wirkung code { font-size: 11px; word-break: break-all; }
.warn { font-size: 12px; color: #6d4c41; background: #fff8e1; border: 1px solid #ffe082;
  border-radius: 6px; padding: 8px 10px; }
.mitglieder { margin: 0 0 12px; padding-left: 18px; font-size: 13px; }
.alert { padding: 8px 12px; border-radius: 6px; font-size: 13px; margin-bottom: 12px;
  cursor: pointer; }
.alert-error { background: #ffebee; border: 1px solid #ef9a9a; color: #c62828; }
.alert-info { background: #e3f2fd; border: 1px solid #90caf9; color: #1565c0; }
</style>
