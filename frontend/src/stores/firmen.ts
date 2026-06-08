import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

export interface Firma {
  id: string
  name: string
  company: string
  unternehmen?: string
  advisor: string
  berater?: string
  description: string
  beschreibung?: string
  frameworks: string[]
  pruefungsfokus: string
  rb_framework: string
  produkt: string
  produktklasse: string
  modules: {
    risikobewertung: boolean
    gutachten: boolean
    cra: boolean
    dsgvo: boolean
    nis2: boolean
    ai_act: boolean
  }
  created_at?: string
  updated_at?: string
}

export interface Produkt {
  id: number
  name: string
  beschreibung?: string
  produktklasse: string
  is_default: number | boolean
}

export interface DeletedFirma {
  name: string
  unternehmen: string
  deleted_at: string
}

export interface Constants {
  rb_frameworks: string[]
  gutachten_frameworks: string[]
  produktklassen: { key: string; label: string }[]
}

export const useFirmenStore = defineStore('firmen', () => {
  const firmen = ref<Firma[]>([])
  const selectedFirma = ref<Firma | null>(null)
  const deletedFirmen = ref<DeletedFirma[]>([])
  const produkte = ref<Produkt[]>([])
  const constants = ref<Constants | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ---- Firmen ----

  const fetchFirmen = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.get('/firmen')
      firmen.value = response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || (err instanceof Error ? err.message : 'Fehler beim Laden')
    } finally {
      loading.value = false
    }
  }

  const fetchFirma = async (name: string): Promise<Firma | null> => {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.get(`/firmen/${encodeURIComponent(name)}`)
      return response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden des Firmen'
      return null
    } finally {
      loading.value = false
    }
  }

  const createFirma = async (data: Partial<Firma> & { name: string }): Promise<Firma | null> => {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.post('/firmen', data)
      const newFirma = response.data
      firmen.value.push(newFirma)
      return newFirma
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Erstellen'
      return null
    } finally {
      loading.value = false
    }
  }

  const updateFirma = async (name: string, data: Partial<Firma>): Promise<Firma | null> => {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.put(`/firmen/${encodeURIComponent(name)}`, data)
      const updated = response.data
      const idx = firmen.value.findIndex(k => k.name === name)
      if (idx >= 0) firmen.value[idx] = updated
      if (selectedFirma.value?.name === name) selectedFirma.value = updated
      return updated
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Aktualisieren'
      return null
    } finally {
      loading.value = false
    }
  }

  const deleteFirma = async (name: string): Promise<boolean> => {
    loading.value = true
    error.value = null
    try {
      await apiClient.delete(`/firmen/${encodeURIComponent(name)}`)
      firmen.value = firmen.value.filter(k => k.name !== name)
      if (selectedFirma.value?.name === name) selectedFirma.value = null
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Löschen'
      return false
    } finally {
      loading.value = false
    }
  }

  const restoreFirma = async (name: string): Promise<boolean> => {
    try {
      const response = await apiClient.post(`/firmen/${encodeURIComponent(name)}/restore`)
      firmen.value.push(response.data)
      deletedFirmen.value = deletedFirmen.value.filter(k => k.name !== name)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Wiederherstellen'
      return false
    }
  }

  const hardDeleteFirma = async (name: string): Promise<boolean> => {
    try {
      await apiClient.delete(`/firmen/${encodeURIComponent(name)}/permanent`)
      deletedFirmen.value = deletedFirmen.value.filter(k => k.name !== name)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim endgültigen Löschen'
      return false
    }
  }

  const fetchDeletedFirmen = async () => {
    try {
      const response = await apiClient.get('/firmen/deleted')
      deletedFirmen.value = response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden gelöschter Firmen'
    }
  }

  // ---- Produkte ----

  const fetchProdukte = async (firmaName: string) => {
    try {
      const response = await apiClient.get(`/firmen/${encodeURIComponent(firmaName)}/produkte`)
      produkte.value = response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Produkte'
    }
  }

  const createProdukt = async (firmaName: string, data: Partial<Produkt>) => {
    try {
      await apiClient.post(`/firmen/${encodeURIComponent(firmaName)}/produkte`, data)
      await fetchProdukte(firmaName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen des Produkts'
      return false
    }
  }

  const updateProdukt = async (firmaName: string, id: number, data: Partial<Produkt>) => {
    try {
      await apiClient.put(`/firmen/${encodeURIComponent(firmaName)}/produkte/${id}`, data)
      await fetchProdukte(firmaName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Aktualisieren des Produkts'
      return false
    }
  }

  const setDefaultProdukt = async (firmaName: string, id: number) => {
    try {
      await apiClient.post(`/firmen/${encodeURIComponent(firmaName)}/produkte/${id}/default`)
      await fetchProdukte(firmaName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Setzen als Standard'
      return false
    }
  }

  const deleteProdukt = async (firmaName: string, id: number) => {
    try {
      await apiClient.delete(`/firmen/${encodeURIComponent(firmaName)}/produkte/${id}`)
      await fetchProdukte(firmaName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Löschen des Produkts'
      return false
    }
  }

  // ---- Evidence ----

  const evidence = ref<any[]>([])

  const fetchEvidence = async (firmaName: string) => {
    try {
      const response = await apiClient.get(`/firmen/${encodeURIComponent(firmaName)}/evidence`)
      evidence.value = response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Evidence'
    }
  }

  const uploadEvidenceFile = async (firmaName: string, file: File, docType: string = '', tags: string[] = []) => {
    const formData = new FormData()
    formData.append('file', file)
    if (docType) formData.append('doc_type', docType)
    if (tags.length) formData.append('tags', tags.join(','))
    try {
      await apiClient.post(`/firmen/${encodeURIComponent(firmaName)}/evidence/file`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      await fetchEvidence(firmaName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Datei-Upload'
      return false
    }
  }

  const addEvidenceUrl = async (firmaName: string, url: string, maxPages: number = 5, docType: string = 'web', tags: string[] = []) => {
    try {
      await apiClient.post(`/firmen/${encodeURIComponent(firmaName)}/evidence/url`, {
        url, max_pages: maxPages, doc_type: docType, tags,
      })
      await fetchEvidence(firmaName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim URL-Crawl'
      return false
    }
  }

  const extractEvidence = async (firmaName: string, docId: string) => {
    try {
      const response = await apiClient.post(`/firmen/${encodeURIComponent(firmaName)}/evidence/${docId}/extract`)
      return response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Text-Extrahieren'
      return null
    }
  }

  const deleteEvidence = async (firmaName: string, docId: string) => {
    try {
      await apiClient.delete(`/firmen/${encodeURIComponent(firmaName)}/evidence/${docId}`)
      evidence.value = evidence.value.filter(e => e.id !== docId)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Löschen'
      return false
    }
  }

  // ---- Konstanten ----

  const fetchConstants = async () => {
    if (constants.value) return constants.value
    try {
      const response = await apiClient.get('/firmen/constants')
      constants.value = response.data
      return response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Konstanten'
      return null
    }
  }

  // ---- Impressum-Parser ----

  const parseImpressum = async (url: string, maxPages: number = 5) => {
    try {
      const response = await apiClient.post('/firmen/parse-impressum', { url, max_pages: maxPages })
      return response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Impressum-Parsen'
      return null
    }
  }

  return {
    firmen,
    selectedFirma,
    deletedFirmen,
    produkte,
    evidence,
    constants,
    loading,
    error,
    fetchFirmen,
    fetchFirma,
    createFirma,
    updateFirma,
    deleteFirma,
    restoreFirma,
    hardDeleteFirma,
    fetchDeletedFirmen,
    fetchProdukte,
    createProdukt,
    updateProdukt,
    setDefaultProdukt,
    deleteProdukt,
    fetchEvidence,
    uploadEvidenceFile,
    addEvidenceUrl,
    extractEvidence,
    deleteEvidence,
    fetchConstants,
    parseImpressum,
  }
})
