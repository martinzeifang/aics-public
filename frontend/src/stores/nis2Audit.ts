import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/nis2-audit'

export interface AuditFinding {
  id: number
  audit_id: number
  beschreibung: string
  schweregrad: string
  massnahme: string
  verantwortlich: string
  frist: string
  status: string
  objekt_typ: string
  objekt_ref: string
}

export interface AuditZyklus {
  ampel: 'grey' | 'green' | 'amber' | 'red'
  status: string
  due_at: string
  days_left?: number
}

export interface Audit {
  id: number
  projekt_name: string
  titel: string
  audit_typ: string
  scope: string
  pruefer: string
  durchgefuehrt_am: string
  naechster_audit_soll: string
  zertifikat_url: string
  zertifikat_ablauf: string
  ergebnis: string
  notizen: string
  findings: AuditFinding[]
  zyklus: AuditZyklus
}

export interface AuditConstants {
  audit_typen: string[]
  audit_ergebnis: string[]
  finding_schweregrade: string[]
  finding_status: string[]
  finding_objekt: string[]
  zyklus_monate: number
}

export const useNis2AuditStore = defineStore('nis2Audit', () => {
  const constants = ref<AuditConstants | null>(null)
  const audits = ref<Audit[]>([])
  const loading = ref(false)
  const error = ref('')

  async function fetchConstants() {
    if (constants.value) return
    try {
      constants.value = (await apiClient.get(`${BASE}/constants`)).data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Konstanten konnten nicht geladen werden.'
    }
  }

  async function fetchAudits(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      audits.value =
        (await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/audits`)).data || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Audits konnten nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function saveAudit(projekt: string, data: Partial<Audit>): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/audits`, data)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
      return false
    }
  }

  async function deleteAudit(projekt: string, pk: number): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.delete(`${BASE}/projekte/${encodeURIComponent(projekt)}/audits/${pk}`)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
      return false
    }
  }

  async function saveFinding(
    projekt: string, auditId: number, data: Partial<AuditFinding>,
  ): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/audits/${auditId}/findings`, data)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Finding speichern fehlgeschlagen.'
      return false
    }
  }

  async function deleteFinding(
    projekt: string, auditId: number, findingId: number,
  ): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.delete(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/audits/${auditId}/findings/${findingId}`)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Finding löschen fehlgeschlagen.'
      return false
    }
  }

  async function exportAudit(projekt: string, auditId: number): Promise<boolean> {
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/audits/${auditId}/export`,
        { responseType: 'blob' })
      const url = URL.createObjectURL(res.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `NIS2-Audit_${projekt}_${auditId}.md`
      a.click()
      URL.revokeObjectURL(url)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Export fehlgeschlagen.'
      return false
    }
  }

  return {
    constants, audits, loading, error,
    fetchConstants, fetchAudits, saveAudit, deleteAudit,
    saveFinding, deleteFinding, exportAudit,
  }
})
