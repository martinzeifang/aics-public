import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

export const useAdminStore = defineStore('admin', () => {
  const settings = ref<any>(null)
  const auditEvents = ref<any[]>([])
  const auditTotal = ref(0)
  const dbList = ref<any[]>([])
  const dbTables = ref<string[]>([])
  const dbRows = ref<any[]>([])
  const dbColumns = ref<string[]>([])
  const dbTotal = ref(0)
  const backups = ref<any[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ---- Settings ----
  const fetchSettings = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/admin/settings')
      settings.value = res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Laden der Einstellungen'
    } finally {
      loading.value = false
    }
  }

  const saveSettings = async (data: any) => {
    loading.value = true
    error.value = null
    try {
      await apiClient.put('/admin/settings', data)
      settings.value = data
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Speichern'
      return false
    } finally {
      loading.value = false
    }
  }

  // ---- Audit ----
  const fetchAuditEvents = async (params: any = {}) => {
    loading.value = true
    try {
      const res = await apiClient.get('/admin/audit/events', { params })
      auditEvents.value = res.data.events || []
      auditTotal.value = res.data.total || 0
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Laden des Audit-Logs'
    } finally {
      loading.value = false
    }
  }

  const auditCsvUrl = (params: any = {}) => {
    const q = new URLSearchParams(params).toString()
    return `/api/admin/audit/export.csv${q ? '?' + q : ''}`
  }

  // #1338: Integritätskette des Audit-Trails prüfen (SHA-256-Verkettung).
  const verifyAuditChain = async (): Promise<{ ok: boolean; count: number; broken_at: number | null }> => {
    const res = await apiClient.get('/admin/audit/verify')
    return res.data
  }

  // ---- DB-Viewer ----
  const fetchDbList = async () => {
    loading.value = true
    try {
      const res = await apiClient.get('/admin/db/list')
      dbList.value = res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Laden der DB-Liste'
    } finally {
      loading.value = false
    }
  }

  const fetchDbTables = async (dbKey: string) => {
    loading.value = true
    try {
      const res = await apiClient.get(`/admin/db/${dbKey}/tables`)
      dbTables.value = res.data.tables || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Laden der Tabellen'
    } finally {
      loading.value = false
    }
  }

  const fetchDbRows = async (dbKey: string, table: string, params: any = {}) => {
    loading.value = true
    try {
      const res = await apiClient.get(`/admin/db/${dbKey}/${table}`, { params })
      dbColumns.value = res.data.columns || []
      dbRows.value = res.data.rows || []
      dbTotal.value = res.data.total || 0
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Laden der Daten'
    } finally {
      loading.value = false
    }
  }

  // ---- Backup ----
  const fetchBackups = async () => {
    loading.value = true
    try {
      const res = await apiClient.get('/admin/backup')
      backups.value = res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Laden der Backups'
    } finally {
      loading.value = false
    }
  }

  const createBackup = async () => {
    loading.value = true
    try {
      // Eine vollständige Sicherung (Datenbank + Dateien) kann bei großen
      // Installationen dauern — das globale Timeout reicht dafür nicht.
      const res = await apiClient.post('/admin/backup', undefined, { timeout: 600000 })
      // Die Antwort des Erstell-Endpunkts trägt kein `format`/`art`; die Liste
      // tut es. Neu laden statt das Fehlende zu erraten — sonst stünde die
      // frische Sicherung ohne Inhaltsangabe in der Tabelle.
      await fetchBackups()
      return res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Erstellen des Backups'
      return null
    } finally {
      loading.value = false
    }
  }

  // #1785: Was in einem Archiv steckt — gelesen **vor** dem Einspielen, damit
  // sichtbar ist, dass ein Archiv im alten Format die Nutzdaten nicht enthält.
  const backupInhalt = async (id: string) => {
    try {
      const res = await apiClient.get(`/admin/backup/${id}/inhalt`)
      return res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Archiv nicht lesbar'
      return null
    }
  }

  /**
   * Abgleich Archiv ↔ aktueller Stand (#1809) — zeigt vor dem Einspielen,
   * was entfernt würde. Scheitert der Abgleich, bleibt der Dialog ohne Zahlen,
   * aber bedienbar: lieber keine Vorschau als ein blockierter Wiederanlauf.
   */
  const backupVorschau = async (id: string, umfang: string = 'fachdaten') => {
    try {
      const res = await apiClient.get(`/admin/backup/${id}/vorschau`, { params: { umfang } })
      return res.data
    } catch {
      return null
    }
  }

  /**
   * Mandanten und Projekte eines Archivs (#1808) — die Auswahlliste für das
   * Übernehmen. Je Position steht dabei, ob es sie hier schon gibt.
   */
  const backupMandanten = async (id: string) => {
    try {
      const res = await apiClient.get(`/admin/backup/${id}/mandanten`)
      return res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Archiv nicht lesbar'
      return null
    }
  }

  /**
   * Daten eines Mandanten **einfügen**, ohne den Bestand zu löschen (#1808/#1810).
   *
   * Der Gegenentwurf zum Restore. `trockenlauf` rechnet alles und schreibt
   * nichts — die Zahlen sind dieselben, nur ohne Wirkung.
   */
  const backupUebernehmen = async (
    id: string,
    mandanten: string[],
    opts: { beiKollision?: string; mitBenutzern?: boolean; mitDateien?: boolean;
            trockenlauf?: boolean } = {},
  ) => {
    try {
      const res = await apiClient.post(`/admin/backup/${id}/uebernehmen`, {
        mandanten,
        bei_kollision: opts.beiKollision || 'behalten',
        mit_benutzern: !!opts.mitBenutzern,
        mit_dateien: opts.mitDateien !== false,
        trockenlauf: !!opts.trockenlauf,
        confirm: id,
      }, { timeout: 600000 })
      return res.data
    } catch (e: any) {
      const d = e?.response?.data
      error.value = (d?.grund ? `${d.error} — ${d.grund}` : d?.error) || 'Übernahme fehlgeschlagen'
      return null
    }
  }

  // #1512: Version- & Update-Kontrolle.
  const versionInfo = ref<any>(null)
  const fetchVersion = async () => {
    try {
      const res = await apiClient.get('/admin/version')
      versionInfo.value = res.data
      return res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Versionsabfrage fehlgeschlagen'
      return null
    }
  }
  /**
   * #1908: Antwort des Servers bei 428 „Rückschritt bestätigen".
   *
   * Als eigener Zustand und nicht als `error`-Text: Die Maske muss die Zahlen
   * (Ziel und aktueller Stand) zeigen und eine Entscheidung einholen — ein
   * Rückschritt setzt älteren Code auf eine Datenbank mit neuerem Schema.
   */
  const updateDowngrade = ref<{ error: string; detail: string; ziel: string; aktuell: string } | null>(null)

  const triggerUpdate = async (body: Record<string, unknown> = {}) => {
    updateDowngrade.value = null
    try {
      const res = await apiClient.post('/admin/update', body)
      return res.data
    } catch (e: any) {
      const d = e?.response?.data
      if (e?.response?.status === 428 && d?.code === 'downgrade-bestaetigen') {
        updateDowngrade.value = d
        // Kein `error`: Das ist eine Rückfrage, kein Fehlschlag. Als Fehler
        // gesetzt stünde die Meldung doppelt — rot unter der Rückfrage.
        return null
      }
      error.value = (d?.detail ? `${d.error}: ${d.detail}` : d?.error) || 'Update fehlgeschlagen'
      return null
    }
  }

  // #1509: Support-Bundle (ZIP aller relevanten Logs) herunterladen.
  const downloadSupportBundle = async () => {
    try {
      const res = await apiClient.get('/admin/support-bundle', { responseType: 'blob' })
      const cd: string = res.headers['content-disposition'] || ''
      const m = cd.match(/filename="?([^"]+)"?/)
      const fname = m ? m[1] : 'support-bundle.zip'
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/zip' }))
      const a = document.createElement('a')
      a.href = url
      a.download = fname
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
      return fname
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Erstellen des Support-Bundles'
      return null
    }
  }

  // Ein Backup, das nur im Container liegt, hilft gegen einen Volume-Verlust
  // nicht — herausholen ließ es sich bisher nur über eine Shell.
  const downloadBackup = async (id: string) => {
    try {
      const res = await apiClient.get(`/admin/backup/${id}/download`, { responseType: 'blob' })
      const cd: string = res.headers['content-disposition'] || ''
      const m = cd.match(/filename="?([^"]+)"?/)
      const fname = m ? m[1] : `${id}.zip`
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/zip' }))
      const a = document.createElement('a')
      a.href = url
      a.download = fname
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
      return fname
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Herunterladen des Backups'
      return null
    }
  }

  const deleteBackup = async (id: string) => {
    try {
      await apiClient.delete(`/admin/backup/${id}`)
      backups.value = backups.value.filter(b => b.id !== id)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Löschen'
      return false
    }
  }

  // Liefert den Bericht des Servers (Zahlen + Warnungen + Hinweis), nicht nur
  // ein „ging gut": Nach einem Restore ist genau das die Information, die
  // zählt — wie viele Tabellen, Zeilen und Dateien eingespielt wurden und was
  // dabei liegen blieb.
  /**
   * Archiv einspielen. `umfang` entscheidet, **was** ersetzt wird (#1813):
   * `fachdaten` lässt Konten, Rollen, Passkeys und den Revisionspfad dieser
   * Installation unangetastet, `alles` ist der Vollumfang für den
   * Wiederanlauf, `nur_benutzer` holt ausschließlich Zugänge zurück.
   */
  const restoreBackup = async (id: string, umfang: string = 'fachdaten') => {
    try {
      const res = await apiClient.post(
        `/admin/backup/${id}/restore`, { confirm: id, umfang }, { timeout: 600000 },
      )
      return res.data
    } catch (e: any) {
      const d = e?.response?.data
      error.value = (d?.detail ? `${d.error} — ${d.detail}` : d?.error) || 'Fehler beim Restore'
      return null
    }
  }

  const uploadBackup = async (file: File) => {
    loading.value = true
    error.value = null
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await apiClient.post('/admin/backup/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
      })
      // Wie beim Erstellen: Format und Umfang stehen erst in der Liste.
      await fetchBackups()
      return res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Upload'
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    settings, auditEvents, auditTotal, dbList, dbTables, dbRows, dbColumns, dbTotal, backups,
    loading, error,
    fetchSettings, saveSettings,
    fetchAuditEvents, auditCsvUrl, verifyAuditChain,
    fetchDbList, fetchDbTables, fetchDbRows,
    versionInfo, fetchVersion, triggerUpdate, updateDowngrade,
    fetchBackups, createBackup, backupInhalt, backupVorschau, downloadSupportBundle, downloadBackup,
    deleteBackup, restoreBackup, uploadBackup,
    backupMandanten, backupUebernehmen,
  }
})
