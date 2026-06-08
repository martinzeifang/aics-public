import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

export interface TiaFields {
  rechtslage: string
  zusatzgarantien: string
  risikoabwaegung: string
  ergebnis: string
}

export interface DsgvoTransfer {
  id?: number
  projekt_name: string
  transfer_id: string
  empfaenger: string
  drittland: string
  grundlage: '' | 'angemessenheit45' | 'scc46' | 'bcr' | 'ausnahme49'
  garantie_detail: string
  tia_status: 'offen' | 'in_arbeit' | 'abgeschlossen' | string
  tia_json: TiaFields
  vvt_ref: string
  avv_ref: string
  created_at?: string
  updated_at?: string
}

const BASE = '/dsgvo-transfer'

export const useDsgvoTransferStore = defineStore('dsgvoTransfer', () => {
  const transfers = ref<DsgvoTransfer[]>([])
  const grundlagen = ref<string[]>([])
  const tiaStatus = ref<string[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  function _msg(e: any, fallback: string): string {
    return e?.response?.data?.error || e?.message || fallback
  }

  async function fetchConstants() {
    try {
      const { data } = await apiClient.get(`${BASE}/constants`)
      grundlagen.value = data.grundlagen || []
      tiaStatus.value = data.tia_status || []
    } catch (e: any) {
      error.value = _msg(e, 'Konstanten konnten nicht geladen werden.')
    }
  }

  async function fetchTransfers(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = null
    try {
      const { data } = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/transfers`,
      )
      transfers.value = data.transfers || []
    } catch (e: any) {
      error.value = _msg(e, 'Transfers konnten nicht geladen werden.')
    } finally {
      loading.value = false
    }
  }

  async function createTransfer(
    projekt: string,
    payload: Partial<DsgvoTransfer>,
  ): Promise<boolean> {
    error.value = null
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/transfers`,
        payload,
      )
      await fetchTransfers(projekt)
      return true
    } catch (e: any) {
      error.value = _msg(e, 'Transfer konnte nicht angelegt werden.')
      return false
    }
  }

  async function updateTransfer(
    projekt: string,
    transferId: string,
    payload: Partial<DsgvoTransfer>,
  ): Promise<boolean> {
    error.value = null
    try {
      await apiClient.put(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/transfers/${encodeURIComponent(transferId)}`,
        payload,
      )
      await fetchTransfers(projekt)
      return true
    } catch (e: any) {
      error.value = _msg(e, 'Transfer konnte nicht gespeichert werden.')
      return false
    }
  }

  async function saveTia(
    projekt: string,
    transferId: string,
    tia: TiaFields,
    tiaStatusValue?: string,
  ): Promise<boolean> {
    error.value = null
    try {
      await apiClient.put(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/transfers/${encodeURIComponent(transferId)}/tia`,
        { tia, tia_status: tiaStatusValue },
      )
      await fetchTransfers(projekt)
      return true
    } catch (e: any) {
      error.value = _msg(e, 'TIA konnte nicht gespeichert werden.')
      return false
    }
  }

  async function deleteTransfer(projekt: string, transferId: string): Promise<boolean> {
    error.value = null
    try {
      await apiClient.delete(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/transfers/${encodeURIComponent(transferId)}`,
      )
      await fetchTransfers(projekt)
      return true
    } catch (e: any) {
      error.value = _msg(e, 'Transfer konnte nicht gelöscht werden.')
      return false
    }
  }

  return {
    transfers,
    grundlagen,
    tiaStatus,
    loading,
    error,
    fetchConstants,
    fetchTransfers,
    createTransfer,
    updateTransfer,
    saveTia,
    deleteTransfer,
  }
})
