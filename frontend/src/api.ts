// Small API client: persona header + number formatting.
/* eslint-disable @typescript-eslint/no-explicit-any */

export type Persona = {
  id: string
  name: string
  role: 'ROLE_FIN_AP' | 'ROLE_SALES_AR' | 'ROLE_CFO_EXEC'
  title: string
  spvs: string[]
  spv_names: Record<string, string>
}

let personaId = (() => {
  try {
    return localStorage.getItem('persona') || 'dewi'
  } catch {
    return 'dewi'
  }
})()

export const getPersonaId = () => personaId
export const setPersonaId = (id: string) => {
  personaId = id
  try {
    localStorage.setItem('persona', id)
  } catch {
    /* browser storage unavailable */
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function call<T = any>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: { 'X-Persona': personaId } }
  if (body instanceof FormData) init.body = body
  else if (body !== undefined) {
    init.body = JSON.stringify(body)
    ;(init.headers as Record<string, string>)['Content-Type'] = 'application/json'
  }
  const res = await fetch(`/api${path}`, init)
  if (!res.ok) {
    let msg = res.statusText
    try {
      const j = await res.json()
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, msg)
  }
  return res.json()
}

export const api = {
  get: <T = any>(p: string) => call<T>('GET', p),
  post: <T = any>(p: string, body?: unknown) => call<T>('POST', p, body ?? {}),
  upload: <T = any>(p: string, form: FormData) => call<T>('POST', p, form),
}

const nf = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
export const rp = (v: number | string | null | undefined) =>
  v === null || v === undefined || v === '' ? '–' : `IDR ${nf.format(Number(v))}`
export const pct = (v: number | string | null | undefined, digits = 0) =>
  v === null || v === undefined || v === '' ? '–' : `${(Number(v) * 100).toFixed(digits)}%`
export const dt = (iso: string) =>
  new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z').toLocaleString('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })

export const ROLE_LABEL: Record<string, string> = {
  ROLE_FIN_AP: 'Finance AP',
  ROLE_SALES_AR: 'Sales Admin AR',
  ROLE_CFO_EXEC: 'CFO',
}

export const STATUS: Record<string, { label: string; tone: 'ok' | 'warn' | 'bad' | 'info' | 'mute' }> = {
  PROCESSING: { label: 'Processing', tone: 'info' },
  READY: { label: 'Ready to approve', tone: 'ok' },
  DISPUTE: { label: 'Dispute', tone: 'bad' },
  HARD_STOP: { label: 'Hard stop', tone: 'bad' },
  MENUNGGU_CFO: { label: 'Awaiting CFO', tone: 'warn' },
  POSTED: { label: 'Posted', tone: 'mute' },
  REJECTED: { label: 'Rejected', tone: 'mute' },
  ERP_GAGAL: { label: 'ERP failed', tone: 'bad' },
  GAGAL_PROSES: { label: 'Processing failed', tone: 'bad' },
  UNALLOCATED: { label: 'Unallocated', tone: 'warn' },
  RECOMMENDED: { label: 'Match ready', tone: 'ok' },
  MANUAL_REVIEW: { label: 'Manual review', tone: 'warn' },
  ALLOCATED: { label: 'Allocated', tone: 'mute' },
}

export const FIELD_LABEL: Record<string, string> = {
  invoice_no: 'Invoice number',
  npwp: 'Vendor tax ID (NPWP)',
  contract_no: 'Contract number',
  progres_klaim: 'Claimed progress (%)',
  progres_bap: 'Inspected progress, BAP (%)',
  tanggal_bap: 'Inspection date',
  bruto_tertulis: 'Stated gross amount',
  ppn_tertulis: 'Stated VAT',
  retensi_tertulis: 'Stated retention',
  pph_tertulis_rate: 'Stated withholding tax rate (%)',
  faktur_nsfp: 'Tax invoice serial',
  faktur_npwp: 'Tax ID on tax invoice',
  faktur_dpp: 'Tax base on tax invoice',
  faktur_ppn: 'VAT on tax invoice',
  progres_disetujui: 'Approved progress (%)',
}
