import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

export interface TemplateSchemaEntry {
  key: string
  typ: string
  beschreibung: string
  pflicht: boolean
}

export interface WordTemplate {
  id: string
  modul: string
  name: string
  version: string | number
  variablen: string[]
  mapping: Record<string, any>
  ist_default: boolean
  aktiv: boolean
  sha256: string
  hochgeladen_am: string
  hochgeladen_von: string
  notizen: string
  schema?: TemplateSchemaEntry[]
}

export const useTemplatesStore = defineStore('templates', () => {
  const templates = ref<WordTemplate[]>([])
  const current = ref<WordTemplate | null>(null)
  const sofficeAvailable = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const fetchHealth = async () => {
    try {
      const res = await apiClient.get('/templates/health')
      sofficeAvailable.value = !!res.data?.soffice_available
      return sofficeAvailable.value
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Health-Check'
      return false
    }
  }

  const fetchTemplates = async (modul: string) => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/templates', { params: { modul } })
      templates.value = res.data || []
      return templates.value
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Vorlagen'
      templates.value = []
      return []
    } finally {
      loading.value = false
    }
  }

  // B1 (#1092): Variablen-Schema eines Moduls OHNE Template-ID — damit der
  // Anwender die {{ tokens }} kennt, bevor er eine Vorlage hochlädt.
  const fetchSchemaForModul = async (modul: string): Promise<TemplateSchemaEntry[]> => {
    try {
      const res = await apiClient.get(`/templates/schema/${encodeURIComponent(modul)}`)
      return (res.data?.schema || []) as TemplateSchemaEntry[]
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden des Variablen-Schemas'
      return []
    }
  }

  const fetchTemplate = async (id: string) => {
    try {
      const res = await apiClient.get(`/templates/${encodeURIComponent(id)}`)
      current.value = res.data
      return res.data as WordTemplate
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Vorlage'
      return null
    }
  }

  const uploadTemplate = async (modul: string, name: string, file: File, notizen?: string) => {
    error.value = null
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('modul', modul)
      fd.append('name', name)
      if (notizen) fd.append('notizen', notizen)
      const res = await apiClient.post('/templates', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return res.data as WordTemplate
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Hochladen'
      return null
    }
  }

  const saveMapping = async (id: string, mapping: Record<string, any>) => {
    try {
      const res = await apiClient.put(`/templates/${encodeURIComponent(id)}/mapping`, { mapping })
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Speichern des Mappings'
      return null
    }
  }

  const setDefault = async (id: string) => {
    try {
      await apiClient.put(`/templates/${encodeURIComponent(id)}/default`)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Setzen der Standard-Vorlage'
      return false
    }
  }

  const deleteTemplate = async (id: string, reason: string) => {
    try {
      await apiClient.delete(`/templates/${encodeURIComponent(id)}`, { data: { reason } })
      templates.value = templates.value.filter(t => t.id !== id)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Löschen'
      return false
    }
  }

  const render = async (id: string, projekt: string, format: 'docx' | 'pdf') => {
    error.value = null
    try {
      const res = await apiClient.post(
        `/templates/${encodeURIComponent(id)}/render`,
        { projekt, format },
        { responseType: 'blob' },
      )
      const blob = new Blob([res.data])
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${projekt || 'export'}.${format}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
      return true
    } catch (err: any) {
      // Fehler-Body kann bei responseType blob ebenfalls ein Blob sein.
      let msg = 'Fehler beim Test-Export'
      const data = err?.response?.data
      if (data instanceof Blob) {
        try {
          const txt = await data.text()
          const parsed = JSON.parse(txt)
          msg = parsed?.error || msg
        } catch { /* Blob nicht lesbar/kein JSON */ }
      } else if (data?.error) {
        msg = data.error
      }
      error.value = msg
      return false
    }
  }

  return {
    templates,
    current,
    sofficeAvailable,
    loading,
    error,
    fetchHealth,
    fetchTemplates,
    fetchSchemaForModul,
    fetchTemplate,
    uploadTemplate,
    saveMapping,
    setDefault,
    deleteTemplate,
    render,
  }
})
