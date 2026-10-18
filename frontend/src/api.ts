// Klien API kecil: header persona + format angka Indonesia.
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
    /* penyimpanan browser tidak tersedia */
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
      /* bukan JSON */
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

const nf = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 })
export const rp = (v: number | string | null | undefined) =>
  v === null || v === undefined || v === '' ? '–' : `Rp${nf.format(Number(v))}`
export const pct = (v: number | string | null | undefined, digits = 0) =>
  v === null || v === undefined || v === '' ? '–' : `${(Number(v) * 100).toFixed(digits).replace('.', ',')}%`
export const dt = (iso: string) =>
  new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z').toLocaleString('id-ID', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })

export const ROLE_LABEL: Record<string, string> = {
  ROLE_FIN_AP: 'Finance AP',
  ROLE_SALES_AR: 'Sales Admin AR',
  ROLE_CFO_EXEC: 'CFO',
}

export const STATUS: Record<string, { label: string; tone: 'ok' | 'warn' | 'bad' | 'info' | 'mute' }> = {
  PROCESSING: { label: 'Diproses', tone: 'info' },
  READY: { label: 'Siap disetujui', tone: 'ok' },
  DISPUTE: { label: 'Dispute', tone: 'bad' },
  HARD_STOP: { label: 'Hard Stop', tone: 'bad' },
  MENUNGGU_CFO: { label: 'Menunggu CFO', tone: 'warn' },
  POSTED: { label: 'Terposting', tone: 'mute' },
  REJECTED: { label: 'Ditolak', tone: 'mute' },
  ERP_GAGAL: { label: 'ERP gagal', tone: 'bad' },
  GAGAL_PROSES: { label: 'Gagal diproses', tone: 'bad' },
  UNALLOCATED: { label: 'Belum teralokasi', tone: 'warn' },
  RECOMMENDED: { label: 'Rekomendasi siap', tone: 'ok' },
  MANUAL_REVIEW: { label: 'Tinjau manual', tone: 'warn' },
  ALLOCATED: { label: 'Teralokasi', tone: 'mute' },
}

export const FIELD_LABEL: Record<string, string> = {
  invoice_no: 'Nomor invoice',
  npwp: 'NPWP vendor',
  contract_no: 'Nomor kontrak',
  progres_klaim: 'Progres klaim (%)',
  progres_bap: 'Progres BAP (%)',
  tanggal_bap: 'Tanggal BAP',
  bruto_tertulis: 'Bruto tertulis',
  ppn_tertulis: 'PPN tertulis',
  retensi_tertulis: 'Retensi tertulis',
  pph_tertulis_rate: 'Tarif PPh di invoice (%)',
  faktur_nsfp: 'Nomor seri faktur',
  faktur_npwp: 'NPWP di faktur',
  faktur_dpp: 'DPP di faktur',
  faktur_ppn: 'PPN di faktur',
  progres_disetujui: 'Progres disetujui (%)',
}
