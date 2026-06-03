import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

export interface Kunde {
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

export interface DeletedKunde {
  name: string
  unternehmen: string
  deleted_at: string
}

export interface Constants {
  rb_frameworks: string[]
  gutachten_frameworks: string[]
  produktklassen: { key: string; label: string }[]
}

export const useKundenStore = defineStore('kunden', () => {
  const kunden = ref<Kunde[]>([])
  const selectedKunde = ref<Kunde | null>(null)
  const deletedKunden = ref<DeletedKunde[]>([])
  const produkte = ref<Produkt[]>([])
  const constants = ref<Constants | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ---- Kunden ----

  const fetchKunden = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.get('/kunden')
      kunden.value = response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || (err instanceof Error ? err.message : 'Fehler beim Laden')
    } finally {
      loading.value = false
    }
  }

  const fetchKunde = async (name: string): Promise<Kunde | null> => {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.get(`/kunden/${encodeURIComponent(name)}`)
      return response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden des Kunden'
      return null
    } finally {
      loading.value = false
    }
  }

  const createKunde = async (data: Partial<Kunde> & { name: string }): Promise<Kunde | null> => {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.post('/kunden', data)
      const newKunde = response.data
      kunden.value.push(newKunde)
      return newKunde
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Erstellen'
      return null
    } finally {
      loading.value = false
    }
  }

  const updateKunde = async (name: string, data: Partial<Kunde>): Promise<Kunde | null> => {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.put(`/kunden/${encodeURIComponent(name)}`, data)
      const updated = response.data
      const idx = kunden.value.findIndex(k => k.name === name)
      if (idx >= 0) kunden.value[idx] = updated
      if (selectedKunde.value?.name === name) selectedKunde.value = updated
      return updated
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Aktualisieren'
      return null
    } finally {
      loading.value = false
    }
  }

  const deleteKunde = async (name: string): Promise<boolean> => {
    loading.value = true
    error.value = null
    try {
      await apiClient.delete(`/kunden/${encodeURIComponent(name)}`)
      kunden.value = kunden.value.filter(k => k.name !== name)
      if (selectedKunde.value?.name === name) selectedKunde.value = null
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Löschen'
      return false
    } finally {
      loading.value = false
    }
  }

  const restoreKunde = async (name: string): Promise<boolean> => {
    try {
      const response = await apiClient.post(`/kunden/${encodeURIComponent(name)}/restore`)
      kunden.value.push(response.data)
      deletedKunden.value = deletedKunden.value.filter(k => k.name !== name)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Wiederherstellen'
      return false
    }
  }

  const hardDeleteKunde = async (name: string): Promise<boolean> => {
    try {
      await apiClient.delete(`/kunden/${encodeURIComponent(name)}/permanent`)
      deletedKunden.value = deletedKunden.value.filter(k => k.name !== name)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim endgültigen Löschen'
      return false
    }
  }

  const fetchDeletedKunden = async () => {
    try {
      const response = await apiClient.get('/kunden/deleted')
      deletedKunden.value = response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden gelöschter Kunden'
    }
  }

  // ---- Produkte ----

  const fetchProdukte = async (kundeName: string) => {
    try {
      const response = await apiClient.get(`/kunden/${encodeURIComponent(kundeName)}/produkte`)
      produkte.value = response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Produkte'
    }
  }

  const createProdukt = async (kundeName: string, data: Partial<Produkt>) => {
    try {
      await apiClient.post(`/kunden/${encodeURIComponent(kundeName)}/produkte`, data)
      await fetchProdukte(kundeName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen des Produkts'
      return false
    }
  }

  const updateProdukt = async (kundeName: string, id: number, data: Partial<Produkt>) => {
    try {
      await apiClient.put(`/kunden/${encodeURIComponent(kundeName)}/produkte/${id}`, data)
      await fetchProdukte(kundeName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Aktualisieren des Produkts'
      return false
    }
  }

  const setDefaultProdukt = async (kundeName: string, id: number) => {
    try {
      await apiClient.post(`/kunden/${encodeURIComponent(kundeName)}/produkte/${id}/default`)
      await fetchProdukte(kundeName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Setzen als Standard'
      return false
    }
  }

  const deleteProdukt = async (kundeName: string, id: number) => {
    try {
      await apiClient.delete(`/kunden/${encodeURIComponent(kundeName)}/produkte/${id}`)
      await fetchProdukte(kundeName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Löschen des Produkts'
      return false
    }
  }

  // ---- Evidence ----

  const evidence = ref<any[]>([])

  const fetchEvidence = async (kundeName: string) => {
    try {
      const response = await apiClient.get(`/kunden/${encodeURIComponent(kundeName)}/evidence`)
      evidence.value = response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Evidence'
    }
  }

  const uploadEvidenceFile = async (kundeName: string, file: File, docType: string = '', tags: string[] = []) => {
    const formData = new FormData()
    formData.append('file', file)
    if (docType) formData.append('doc_type', docType)
    if (tags.length) formData.append('tags', tags.join(','))
    try {
      await apiClient.post(`/kunden/${encodeURIComponent(kundeName)}/evidence/file`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      await fetchEvidence(kundeName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Datei-Upload'
      return false
    }
  }

  const addEvidenceUrl = async (kundeName: string, url: string, maxPages: number = 5, docType: string = 'web', tags: string[] = []) => {
    try {
      await apiClient.post(`/kunden/${encodeURIComponent(kundeName)}/evidence/url`, {
        url, max_pages: maxPages, doc_type: docType, tags,
      })
      await fetchEvidence(kundeName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim URL-Crawl'
      return false
    }
  }

  const extractEvidence = async (kundeName: string, docId: string) => {
    try {
      const response = await apiClient.post(`/kunden/${encodeURIComponent(kundeName)}/evidence/${docId}/extract`)
      return response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Text-Extrahieren'
      return null
    }
  }

  const deleteEvidence = async (kundeName: string, docId: string) => {
    try {
      await apiClient.delete(`/kunden/${encodeURIComponent(kundeName)}/evidence/${docId}`)
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
      const response = await apiClient.get('/kunden/constants')
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
      const response = await apiClient.post('/kunden/parse-impressum', { url, max_pages: maxPages })
      return response.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Impressum-Parsen'
      return null
    }
  }

  return {
    kunden,
    selectedKunde,
    deletedKunden,
    produkte,
    evidence,
    constants,
    loading,
    error,
    fetchKunden,
    fetchKunde,
    createKunde,
    updateKunde,
    deleteKunde,
    restoreKunde,
    hardDeleteKunde,
    fetchDeletedKunden,
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
