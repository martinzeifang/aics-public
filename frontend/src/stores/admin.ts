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
      const res = await apiClient.post('/admin/backup')
      backups.value.unshift(res.data)
      return res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Erstellen des Backups'
      return null
    } finally {
      loading.value = false
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

  const restoreBackup = async (id: string) => {
    try {
      await apiClient.post(`/admin/backup/${id}/restore`, { confirm: id })
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Restore'
      return false
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
      backups.value.unshift(res.data)
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
    fetchBackups, createBackup, deleteBackup, restoreBackup, uploadBackup,
  }
})
