/* eslint-disable @typescript-eslint/no-explicit-any */
import { Alert, Box, Button, LinearProgress, Paper, Snackbar, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, dt, FIELD_LABEL, pct, rp, STATUS } from '../api'
import { SEV, Section, StatusChip } from '../components/bits'
import { C } from '../theme'

const ACTION_LABEL: Record<string, string> = {
  UPLOAD: 'Unggah dokumen', PROCESSED: 'Diproses agen', OVERRIDE: 'Override nilai', SET_CONTRACT: 'Hubungkan kontrak',
  POST: 'Setujui & posting', POST_ERP: 'Kirim ke ERP', SUBMIT_CFO: 'Ajukan ke CFO', CFO_APPROVE: 'CFO menyetujui',
  CFO_REJECT: 'CFO menolak', CFO_UNLOCK: 'CFO membuka kunci', REJECT: 'Tolak', FLAG: 'Tandai dispute', RESEND: 'Kirim ulang',
  RETRY: 'Proses ulang', UPLOAD_CSV: 'Unggah rekening koran', ALLOCATE: 'Alokasi penerimaan', RECALC_CHANGED: 'Hitung ulang berubah',
  CFO_WAIVER_APPROVE: 'CFO setujui waiver', CFO_WAIVER_REJECT: 'CFO tolak waiver', SEED: 'Data awal',
}

export default function Cfo() {
  const nav = useNavigate()
  const [queue, setQueue] = useState<any[] | null>(null)
  const [log, setLog] = useState<any[]>([])
  const [acc, setAcc] = useState<any[]>([])
  const [verify, setVerify] = useState<any>(null)
  const [toast, setToast] = useState<{ msg: string; err?: boolean } | null>(null)

  const load = useCallback(() => {
    api.get('/cfo/queue').then(setQueue).catch((e) => setToast({ msg: e.message, err: true }))
    api.get('/audit?limit=60').then(setLog)
    api.get('/accuracy').then(setAcc)
  }, [])
  useEffect(load, [load])

  const waiver = async (id: number, approve: boolean) => {
    try {
      await api.post(`/cfo/waiver/${id}`, { approve, reason: approve ? 'Disetujui CFO' : 'Tidak memenuhi kebijakan waiver' })
      setToast({ msg: approve ? 'Waiver disetujui; denda dihapus.' : 'Waiver ditolak; denda ditagihkan ke pembeli.' })
      load()
    } catch (e) {
      setToast({ msg: (e as Error).message, err: true })
    }
  }

  if (!queue) return <LinearProgress />
  return (
    <Box>
      <Typography variant="h1" sx={{ mb: 0.5 }}>Ruang CFO</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>Keputusan yang hanya bisa diambil oleh Anda, jejak audit, dan akurasi agen.</Typography>

      <Section title="Menunggu keputusan Anda">
        <Paper>
          <Table size="small">
            <TableHead><TableRow><TableCell>Jenis</TableCell><TableCell>SPV</TableCell><TableCell>Referensi</TableCell>
              <TableCell align="right">Nilai</TableCell><TableCell>Alasan</TableCell><TableCell>Status</TableCell><TableCell align="right" /></TableRow></TableHead>
            <TableBody>
              {queue.map((q) => (
                <TableRow key={q.kind + q.id}>
                  <TableCell>{q.kind === 'AP' ? 'Tagihan' : 'Waiver denda'}</TableCell>
                  <TableCell>{q.spv}</TableCell>
                  <TableCell>{q.ref}</TableCell>
                  <TableCell align="right">{rp(q.amount)}</TableCell>
                  <TableCell sx={{ maxWidth: 360 }}>
                    {q.kind === 'AP' ? q.anomalies.filter((a: any) => a.severity !== 'MEDIUM').map((a: any, i: number) => (
                      <Typography key={i} variant="body2" sx={{ color: SEV[a.severity].fg }}>{a.message}</Typography>
                    )) : <Typography variant="body2">{q.waiver?.justification}</Typography>}
                  </TableCell>
                  <TableCell>{q.kind === 'AP' ? <StatusChip status={q.status} /> : <StatusChip status="MENUNGGU_CFO" />}</TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                    {q.kind === 'AP' ? <Button variant="outlined" size="small" onClick={() => nav(`/ap/${q.id}`)}>Tinjau</Button> : (
                      <>
                        <Button size="small" onClick={() => waiver(q.id, true)}>Setujui</Button>
                        <Button size="small" color="error" onClick={() => waiver(q.id, false)}>Tolak</Button>
                      </>)}
                  </TableCell>
                </TableRow>
              ))}
              {!queue.length && <TableRow><TableCell colSpan={7} sx={{ py: 3, textAlign: 'center', color: 'text.secondary' }}>Tidak ada yang menunggu keputusan Anda.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </Paper>
      </Section>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 2fr' }, gap: 2 }}>
        <Section title="Akurasi agen pembaca dokumen">
          <Paper>
            <Table size="small">
              <TableHead><TableRow><TableCell>Field</TableCell><TableCell align="right">Dokumen</TableCell><TableCell align="right">Dikoreksi</TableCell><TableCell align="right">Akurasi</TableCell></TableRow></TableHead>
              <TableBody>
                {acc.map((a) => (
                  <TableRow key={a.field}>
                    <TableCell>{FIELD_LABEL[a.field]}</TableCell>
                    <TableCell align="right">{a.total}</TableCell>
                    <TableCell align="right">{a.overridden}</TableCell>
                    <TableCell align="right">{a.accuracy === null ? '–' : pct(a.accuracy)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
          <Typography variant="caption" color="text.secondary">Akurasi = field yang tidak dikoreksi manusia dibagi seluruh field yang dibaca.</Typography>
        </Section>

        <Section title="Jejak audit"
          action={<>
            <Button size="small" onClick={() => api.get('/audit/verify').then(setVerify)}>Verifikasi integritas</Button>
            <Button size="small" color="error" onClick={() => api.post('/demo/tamper').then(() => api.get('/audit/verify').then(setVerify))}>
              Simulasi ubah data
            </Button>
          </>}>
          {verify && (
            <Alert severity={verify.ok ? 'success' : 'error'} sx={{ mb: 1 }}>
              {verify.ok ? `Rantai hash utuh: ${verify.checked} entri terverifikasi.` :
                `Rantai hash putus di entri #${verify.broken_at}. Data telah diubah di luar aplikasi.`}
            </Alert>)}
          <Paper sx={{ maxHeight: 460, overflowY: 'auto' }}>
            <Table size="small" stickyHeader>
              <TableHead><TableRow><TableCell>Waktu</TableCell><TableCell>Pelaku</TableCell><TableCell>Aksi</TableCell><TableCell>Objek</TableCell><TableCell>Alasan</TableCell></TableRow></TableHead>
              <TableBody>
                {log.map((e) => (
                  <TableRow key={e.id} sx={{ bgcolor: verify && !verify.ok && verify.broken_at === e.id ? C.badSoft : undefined }}>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>{dt(e.ts)}</TableCell>
                    <TableCell>{e.actor}</TableCell>
                    <TableCell>{ACTION_LABEL[e.action] ?? e.action}</TableCell>
                    <TableCell>{e.entity === 'termin' ? `Tagihan #${e.entity_id}` : e.entity === 'receipt' ? (e.entity_id ? `Penerimaan #${e.entity_id}` : 'Rekening koran') : e.entity}
                      {e.after?.status ? `: ${STATUS[e.after.status]?.label ?? e.after.status}` : ''}</TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{e.reason}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        </Section>
      </Box>
      <Snackbar open={!!toast} autoHideDuration={6000} onClose={() => setToast(null)}>
        {toast ? <Alert severity={toast.err ? 'error' : 'success'} onClose={() => setToast(null)}>{toast.msg}</Alert> : undefined}
      </Snackbar>
    </Box>
  )
}
