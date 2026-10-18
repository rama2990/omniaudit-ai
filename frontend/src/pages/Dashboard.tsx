import UploadFileOutlined from '@mui/icons-material/UploadFileOutlined'
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Divider, Paper, Snackbar, Table, TableBody,
  TableCell, TableHead, TableRow, TextField, ToggleButton, ToggleButtonGroup, Typography,
} from '@mui/material'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, rp } from '../api'
import { ScoreBadge, SevDot, StatusChip } from '../components/bits'
import { useSession } from '../session'
import { C } from '../theme'

type Item = {
  kind: 'AP' | 'AR'; id: number; spv: string; party: string; ref: string; amount: number; status: string
  score: number; severities: string[]; needs_cfo: boolean; at: string
}
type Metrics = {
  unallocated_ar: number; unallocated_count: number; pending_ap: number; pending_ap_count: number
  flagged: number; velocity_min: number | null; leakage_prevented: number
}
const ACTIVE = ['PROCESSING', 'READY', 'DISPUTE', 'HARD_STOP', 'MENUNGGU_CFO', 'ERP_GAGAL', 'GAGAL_PROSES',
  'UNALLOCATED', 'RECOMMENDED', 'MANUAL_REVIEW']

function Metric({ label, value, note, tone }: { label: string; value: string; note?: string; tone?: string }) {
  return (
    <Box sx={{ flex: '1 1 180px', px: 2.5, py: 2 }}>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
      <Typography sx={{ fontSize: 26, fontWeight: 500, color: tone ?? C.ink, fontVariantNumeric: 'tabular-nums', mt: 0.5 }}>
        {value}
      </Typography>
      {note && <Typography variant="caption" color="text.secondary">{note}</Typography>}
    </Box>
  )
}

export default function Dashboard() {
  const { persona, spv } = useSession()
  const nav = useNavigate()
  const [m, setM] = useState<Metrics | null>(null)
  const [items, setItems] = useState<Item[]>([])
  const [filter, setFilter] = useState<'aktif' | 'AP' | 'AR' | 'semua'>('aktif')
  const [flag, setFlag] = useState<Item | null>(null)
  const [reason, setReason] = useState('')
  const [toast, setToast] = useState<{ msg: string; err?: boolean } | null>(null)
  const [busy, setBusy] = useState(false)
  const apFile = useRef<HTMLInputElement>(null)
  const arFile = useRef<HTMLInputElement>(null)

  const load = useCallback(() => {
    if (!spv) return
    api.get(`/dashboard?spv=${spv}`).then(setM).catch((e) => setToast({ msg: e.message, err: true }))
    api.get(`/queue?spv=${spv}`).then(setItems)
  }, [spv])
  useEffect(load, [load])
  useEffect(() => {
    if (!items.some((i) => i.status === 'PROCESSING')) return
    const t = setInterval(load, 2000)
    return () => clearInterval(t)
  }, [items, load])

  if (!persona) return null
  const role = persona.role
  const uploadSpv = spv === 'ALL' ? persona.spvs[0] : spv
  const shown = items.filter((i) =>
    filter === 'semua' ? true : filter === 'aktif' ? ACTIVE.includes(i.status) : i.kind === filter && ACTIVE.includes(i.status))

  const uploadAp = async (f: File) => {
    const fd = new FormData()
    fd.append('spv', uploadSpv)
    fd.append('file', f)
    setBusy(true)
    try {
      const r = await api.upload('/ap/upload', fd)
      nav(`/ap/${r.id}`)
    } catch (e) {
      setToast({ msg: (e as Error).message, err: true })
    } finally {
      setBusy(false)
    }
  }
  const uploadAr = async (f: File) => {
    const fd = new FormData()
    fd.append('spv', uploadSpv)
    fd.append('file', f)
    setBusy(true)
    try {
      const s = await api.upload('/ar/upload', fd)
      setToast({ msg: `${s.rows} penerimaan dibaca: ${s.auto} otomatis teralokasi lewat VA, ${s.recommended} siap dikonfirmasi, ${s.manual} perlu tinjau manual${s.duplicates ? `, ${s.duplicates} kemungkinan duplikat` : ''}.` })
      load()
    } catch (e) {
      setToast({ msg: (e as Error).message, err: true })
    } finally {
      setBusy(false)
    }
  }

  const approve = async (i: Item) => {
    try {
      if (i.kind === 'AP') {
        const t = await api.post(`/ap/termin/${i.id}/action`, { action: 'post' })
        setToast({ msg: t.status === 'POSTED' ? `Terposting ke ERP: ${t.erp_ref}` : `Status: ${t.status}` })
      } else {
        const d = await api.get(`/ar/receipt/${i.id}`)
        await api.post(`/ar/receipt/${i.id}/confirm`, { unit_id: d.selected_unit.id })
        setToast({ msg: `Dialokasikan ke unit ${d.selected_unit.code} dan notifikasi dikirim ke pembeli.` })
      }
      load()
    } catch (e) {
      setToast({ msg: (e as Error).message, err: true })
    }
  }

  const doFlag = async () => {
    if (!flag) return
    try {
      await api.post(`/ap/termin/${flag.id}/action`, { action: 'flag', reason })
      setFlag(null)
      setReason('')
      load()
    } catch (e) {
      setToast({ msg: (e as Error).message, err: true })
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Box sx={{ flex: 1, minWidth: 260 }}>
          <Typography variant="h1">Selamat datang, {persona.name.split(' ')[0]}</Typography>
          <Typography color="text.secondary">
            {spv === 'ALL' ? 'Semua SPV' : persona.spv_names[spv]}: transaksi yang menunggu keputusan Anda ada di bawah.
          </Typography>
        </Box>
        {role === 'ROLE_FIN_AP' && (
          <Button variant="contained" startIcon={<UploadFileOutlined />} disabled={busy} onClick={() => apFile.current?.click()}>
            Unggah dokumen tagihan
          </Button>
        )}
        {role === 'ROLE_SALES_AR' && (
          <Button variant="contained" startIcon={<UploadFileOutlined />} disabled={busy} onClick={() => arFile.current?.click()}>
            Unggah rekening koran
          </Button>
        )}
        <input ref={apFile} type="file" accept="application/pdf" hidden
          onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) uploadAp(f) }} />
        <input ref={arFile} type="file" accept=".csv,text/csv" hidden
          onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) uploadAr(f) }} />
      </Box>

      {m && (
        <Paper sx={{ display: 'flex', flexWrap: 'wrap', mb: 3, '& > div + div': { borderLeft: { md: `1px solid ${C.outline}` } } }}>
          <Metric label="Dana pembeli belum teralokasi" value={rp(m.unallocated_ar)} note={`${m.unallocated_count} penerimaan`} />
          <Metric label="Tagihan kontraktor menunggu audit" value={rp(m.pending_ap)} note={`${m.pending_ap_count} termin, nilai terverifikasi`} />
          <Metric label="Dispute & Hard Stop" value={String(m.flagged)} tone={m.flagged ? C.bad : C.ink} note="termin terkunci" />
          <Metric label="Rata-rata waktu audit" value={m.velocity_min !== null ? `${m.velocity_min.toString().replace('.', ',')} mnt` : '–'} note="unggah sampai terposting, 30 hari" />
          <Metric label="Kebocoran dicegah" value={rp(m.leakage_prevented)} tone={C.ok} note="klaim dikurangi nilai terverifikasi" />
        </Paper>
      )}

      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1, gap: 2 }}>
        <Typography variant="h2" sx={{ flex: 1 }}>Antrean staging</Typography>
        <ToggleButtonGroup size="small" exclusive value={filter} onChange={(_, v) => v && setFilter(v)}>
          <ToggleButton value="aktif">Perlu tindakan</ToggleButton>
          <ToggleButton value="AP">Tagihan kontraktor</ToggleButton>
          <ToggleButton value="AR">Penerimaan pembeli</ToggleButton>
          <ToggleButton value="semua">Semua</ToggleButton>
        </ToggleButtonGroup>
      </Box>
      <Paper sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Jenis</TableCell>
              <TableCell>SPV</TableCell>
              <TableCell>Pihak</TableCell>
              <TableCell>Referensi</TableCell>
              <TableCell align="right">Nilai</TableCell>
              <TableCell>Skor</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Aksi</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {shown.map((i) => {
              const canApprove = (i.kind === 'AP' && i.status === 'READY' && role === 'ROLE_FIN_AP') ||
                (i.kind === 'AR' && i.status === 'RECOMMENDED' && role === 'ROLE_SALES_AR')
              return (
                <TableRow key={i.kind + i.id} hover>
                  <TableCell>{i.kind === 'AP' ? 'Tagihan' : 'Penerimaan'}</TableCell>
                  <TableCell>{i.spv}</TableCell>
                  <TableCell sx={{ maxWidth: 220 }}>{i.party}</TableCell>
                  <TableCell sx={{ maxWidth: 260, color: 'text.secondary' }}>
                    {i.severities.map((s) => <SevDot key={s} sev={s} />)}
                    {i.ref}
                  </TableCell>
                  <TableCell align="right">{i.amount ? rp(i.amount) : '–'}</TableCell>
                  <TableCell>{i.status === 'PROCESSING' ? '–' : (
                    <ScoreBadge score={i.score} title={i.kind === 'AP' ? 'Skor Kepastian ekstraksi AI' : 'Match Score unit'} />)}
                  </TableCell>
                  <TableCell>
                    <StatusChip status={i.status} />
                    {i.needs_cfo && i.status === 'DISPUTE' && (
                      <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>butuh CFO</Typography>)}
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                    {canApprove && <Button size="small" onClick={() => approve(i)}>Setujui</Button>}
                    {i.kind === 'AP' && i.status === 'READY' && role === 'ROLE_FIN_AP' && (
                      <Button size="small" color="error" onClick={() => setFlag(i)}>Tandai dispute</Button>)}
                    <Button size="small" variant="outlined" onClick={() => nav(`/${i.kind.toLowerCase()}/${i.id}`)}>Tinjau</Button>
                  </TableCell>
                </TableRow>
              )
            })}
            {!shown.length && (
              <TableRow>
                <TableCell colSpan={8} sx={{ py: 4, textAlign: 'center', color: 'text.secondary' }}>
                  Tidak ada transaksi di filter ini.{' '}
                  {role === 'ROLE_FIN_AP' ? 'Unggah dokumen tagihan untuk memulai.' :
                    role === 'ROLE_SALES_AR' ? 'Unggah rekening koran untuk memulai.' : ''}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>

      <Dialog open={!!flag} onClose={() => setFlag(null)} fullWidth maxWidth="sm">
        <DialogTitle>Tandai sebagai dispute</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Termin akan dikunci dan harus ditinjau di layar audit sebelum bisa diposting.
          </Typography>
          <TextField autoFocus fullWidth multiline minRows={2} label="Alasan (minimal 10 karakter)" value={reason}
            onChange={(e) => setReason(e.target.value)} />
        </DialogContent>
        <Divider />
        <DialogActions>
          <Button onClick={() => setFlag(null)}>Batal</Button>
          <Button variant="contained" color="error" disabled={reason.trim().length < 10} onClick={doFlag}>Tandai dispute</Button>
        </DialogActions>
      </Dialog>
      <Snackbar open={!!toast} autoHideDuration={6000} onClose={() => setToast(null)}>
        {toast ? <Alert severity={toast.err ? 'error' : 'success'} onClose={() => setToast(null)}>{toast.msg}</Alert> : undefined}
      </Snackbar>
    </Box>
  )
}
