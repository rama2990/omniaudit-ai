/* eslint-disable @typescript-eslint/no-explicit-any */
import ArrowBack from '@mui/icons-material/ArrowBack'
import EditOutlined from '@mui/icons-material/EditOutlined'
import PlaceOutlined from '@mui/icons-material/PlaceOutlined'
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, LinearProgress, MenuItem,
  Paper, Snackbar, Table, TableBody, TableCell, TableHead, TableRow, TextField, Tooltip, Typography,
} from '@mui/material'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, FIELD_LABEL, getPersonaId, pct, rp } from '../api'
import { ScoreBadge, SEV, Section, StatusChip } from '../components/bits'
import PdfEvidence, { type EvidenceBox } from '../components/PdfEvidence'
import { C } from '../theme'

const ROWS: [string, string, string[]][] = [
  ['np', 'Nilai progres termin', ['progres_klaim', 'progres_bap']],
  ['um', 'Potongan uang muka', []],
  ['dpp_faktur', 'DPP faktur', ['faktur_dpp']],
  ['ppn', 'PPN 11%', ['ppn_tertulis', 'faktur_ppn']],
  ['bruto', 'Bruto tagihan', ['bruto_tertulis']],
  ['ret', 'Retensi', ['retensi_tertulis']],
  ['pen', 'Potongan denda keterlambatan', ['tanggal_bap']],
  ['pph', 'PPh 4(2)', ['pph_tertulis_rate']],
]
const ACTION: Record<string, { label: string; color?: 'error' | 'primary'; variant?: 'contained' | 'outlined'; reason?: boolean }> = {
  post: { label: 'Setujui & posting ke ERP', variant: 'contained' },
  submit_cfo: { label: 'Ajukan ke CFO', variant: 'contained' },
  cfo_approve: { label: 'Setujui & posting ke ERP', variant: 'contained' },
  cfo_unlock: { label: 'Buka kunci untuk ditinjau', variant: 'outlined', reason: true },
  resend: { label: 'Kirim ulang ke ERP', variant: 'contained' },
  retry: { label: 'Proses ulang', variant: 'contained' },
  flag: { label: 'Tandai dispute', color: 'error', variant: 'outlined', reason: true },
  reject: { label: 'Tolak tagihan', color: 'error', variant: 'outlined', reason: true },
  cfo_reject: { label: 'Tolak tagihan', color: 'error', variant: 'outlined', reason: true },
}
const AGENT_COLOR: Record<string, string> = {
  'Parser Agent': C.blue, 'Contract Agent': '#9334E6', 'Adversarial Auditor': C.bad, 'Mesin Kalkulasi': C.ok, Sistem: C.muted,
}

export default function ApReview() {
  const { id } = useParams()
  const [t, setT] = useState<any>(null)
  const [events, setEvents] = useState<any[]>([])
  const [focus, setFocus] = useState<string | null>(null)
  const [dlg, setDlg] = useState<{ action: string; field?: string; value?: string } | null>(null)
  const [reason, setReason] = useState('')
  const [toast, setToast] = useState<{ msg: string; err?: boolean } | null>(null)
  const logBox = useRef<HTMLDivElement>(null)

  const load = useCallback(() => api.get(`/ap/termin/${id}`).then((d) => { setT(d); setEvents(d.telemetry) }), [id])
  useEffect(() => { load().catch((e) => setToast({ msg: e.message, err: true })) }, [load])

  const processing = t?.status === 'PROCESSING'
  useEffect(() => {
    if (!processing) return
    setEvents([])
    const es = new EventSource(`/api/ap/termin/${id}/events?persona=${getPersonaId()}`)
    es.onmessage = (e) => setEvents((x) => [...x, JSON.parse(e.data)])
    es.addEventListener('done', () => { es.close(); load() })
    es.onerror = () => { es.close(); setTimeout(load, 1500) }
    return () => es.close()
  }, [processing, id, load])
  useEffect(() => { const b = logBox.current; if (b) b.scrollTop = b.scrollHeight }, [events.length])

  const boxes: EvidenceBox[] = useMemo(() => (t?.fields ?? []).flatMap((f: any) =>
    f.boxes.map((b: any) => ({ key: f.name, page: b.page, bbox: b.bbox, tone: f.hot ? 'bad' : 'ok',
      label: `${FIELD_LABEL[f.name] ?? f.name}: ${f.value}` }))), [t])
  const has = (k: string) => boxes.some((b) => b.key === k)

  if (!t) return <LinearProgress />
  const cc = t.calc_claim, cv = t.calc_verified
  const editable = t.actions.includes('override')

  const run = async (action: string, extra: Record<string, unknown> = {}) => {
    try {
      const d = await api.post(`/ap/termin/${id}/action`, { action, reason, ...extra })
      setT(d)
      setEvents(d.telemetry)
      setDlg(null)
      setReason('')
      const msg: Record<string, string> = {
        POSTED: `Terposting ke ERP. Nomor batch: ${d.erp_ref}`, MENUNGGU_CFO: 'Diajukan ke CFO.', REJECTED: 'Tagihan ditolak.',
        ERP_GAGAL: 'ERP menolak batch jurnal. Data tersimpan; kirim ulang saat ERP tersedia.', DISPUTE: 'Termin dikunci sebagai dispute.',
      }
      setToast({ msg: action === 'override' || action === 'set_contract' ? 'Nilai diperbarui dan dihitung ulang.' : (msg[d.status] ?? `Status: ${d.status}`), err: d.status === 'ERP_GAGAL' })
    } catch (e) {
      setToast({ msg: (e as Error).message, err: true })
    }
  }

  const visibleActions = t.actions.filter((a: string) => ACTION[a])
  const leak = cc?.net && cv?.net ? Number(cc.net) - Number(cv.net) : 0

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <IconButton component={Link} to="/" aria-label="Kembali ke antrean"><ArrowBack /></IconButton>
        <Box sx={{ flex: 1, minWidth: 240 }}>
          <Typography variant="h1">{t.vendor?.name ?? t.filename}</Typography>
          <Typography color="text.secondary">
            {t.contract ? `${t.contract.no}, ${t.contract.name}` : 'Kontrak belum terhubung'}
          </Typography>
        </Box>
        <StatusChip status={t.status} size="medium" />
        {!processing && <ScoreBadge score={Number(t.confidence)} title="Skor Kepastian: keyakinan terendah di antara field wajib" />}
        {t.mode && <Chip size="small" variant="outlined" label={t.mode === 'gemini' ? `Dibaca oleh ${t.model}` : t.mode === 'fake' ? 'Dibaca pola teks lokal' : 'Arsip'} />}
      </Box>

      {t.status === 'DISPUTE' && t.needs_cfo && (
        <Alert severity="warning" sx={{ mb: 2 }}>Nilai klaim di atas Rp500 juta. Setelah ditinjau, termin ini harus disetujui CFO sebelum diposting.</Alert>)}
      {t.fallback && <Alert severity="info" sx={{ mb: 2 }}>Gemini tidak tersedia saat dokumen ini diproses ({t.fallback}). Dokumen dibaca dengan pola teks lokal; periksa nilai bertanda sebelum menyetujui.</Alert>}
      {t.erp_ref && <Alert severity="success" sx={{ mb: 2 }}>Jurnal terposting ke ERP dengan nomor batch {t.erp_ref}.</Alert>}
      {t.error && t.status !== 'POSTED' && <Alert severity="error" sx={{ mb: 2 }}>{t.error}</Alert>}

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2 }}>
        <Paper sx={{ height: { md: 'calc(100vh - 210px)' }, minHeight: 480, overflow: 'hidden', position: { md: 'sticky' }, top: { md: 88 } }}>
          {t.pages.length ? (
            <PdfEvidence url={`/api/ap/termin/${id}/pdf?persona=${getPersonaId()}`} pages={t.pages} boxes={boxes}
              focus={focus} onFocus={setFocus} />
          ) : (
            <Box sx={{ p: 3 }}><Typography color="text.secondary">Dokumen sedang dibaca…</Typography><LinearProgress sx={{ mt: 2 }} /></Box>
          )}
        </Paper>

        <Box>
          {t.anomalies.length > 0 && (
            <Section title="Temuan auditor">
              {t.anomalies.map((a: any, i: number) => (
                <Box key={i} sx={{ display: 'flex', gap: 1.5, p: 1.25, mb: 0.75, borderRadius: 1, bgcolor: SEV[a.severity].bg }}>
                  <Typography variant="body2" sx={{ color: SEV[a.severity].fg, fontWeight: 600, minWidth: 52 }}>{SEV[a.severity].label}</Typography>
                  <Typography variant="body2">{a.message}</Typography>
                </Box>
              ))}
            </Section>
          )}

          {cv?.net !== undefined && (
            <Section title="Klaim kontraktor dibandingkan hasil verifikasi BAP">
              <Paper>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell />
                      <TableCell align="right">Klaim invoice ({pct(cc.p)})</TableCell>
                      <TableCell align="right">Terverifikasi ({pct(cv.p)})</TableCell>
                      <TableCell align="right">Selisih</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {ROWS.map(([k, label, ev]) => {
                      const diff = Number(cc[k]) - Number(cv[k])
                      const link = ev.find(has)
                      return (
                        <TableRow key={k}>
                          <TableCell>
                            {label}
                            {link && (
                              <Tooltip title="Tunjukkan di dokumen">
                                <IconButton size="small" onClick={() => setFocus(link)} aria-label={`Tunjukkan ${label} di dokumen`}>
                                  <PlaceOutlined fontSize="inherit" />
                                </IconButton>
                              </Tooltip>)}
                          </TableCell>
                          <TableCell align="right">{rp(cc[k])}</TableCell>
                          <TableCell align="right">{rp(cv[k])}</TableCell>
                          <TableCell align="right" sx={{ color: diff ? C.bad : C.muted }}>{diff ? rp(diff) : '–'}</TableCell>
                        </TableRow>
                      )
                    })}
                    <TableRow sx={{ '& td': { fontWeight: 700, fontSize: 15, borderBottom: 0 } }}>
                      <TableCell>Net payable</TableCell>
                      <TableCell align="right">{rp(cc.net)}</TableCell>
                      <TableCell align="right">{rp(cv.net)}</TableCell>
                      <TableCell align="right" sx={{ color: leak ? `${C.ok} !important` : undefined }}>{leak ? rp(leak) : '–'}</TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
                {leak > 0 && (
                  <Typography variant="body2" sx={{ px: 1.5, pb: 1.5, color: C.ok }}>
                    Verifikasi mencegah kelebihan bayar {rp(leak)}.
                  </Typography>)}
              </Paper>
            </Section>
          )}

          {t.contract && (
            <Section title="Ketentuan kontrak & pajak">
              <Paper sx={{ p: 1.5, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: 1.5 }}>
                {[
                  ['DPP kontrak', rp(t.contract.dpp_kontrak)],
                  ['Vendor', `${t.vendor.jenis.toLowerCase()}, SBU ${t.vendor.sbu.toLowerCase()}`],
                  ['Tarif PPh 4(2)', pct(t.summary.pph_rate, 2)],
                  ['Retensi', pct(t.contract.ret_pct)],
                  ['Uang muka', `${pct(t.contract.um_pct)}, saldo ${rp(t.summary.um_saldo)}`],
                  ['Progres sebelumnya', pct(t.summary.progres_sebelumnya)],
                  ['Target selesai', new Date(t.contract.target_date).toLocaleDateString('id-ID', { dateStyle: 'medium' })],
                  ['Hari terlambat', t.summary.late_days ? `${t.summary.late_days} hari` : 'Tidak terlambat'],
                  ['Sisa denda terbawa', rp(t.summary.pen_left)],
                ].map(([k, v]) => (
                  <Box key={k}>
                    <Typography variant="caption" color="text.secondary">{k}</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>{v}</Typography>
                  </Box>
                ))}
              </Paper>
            </Section>
          )}

          {t.fields.length > 0 && (
            <Section title="Data yang dibaca dari dokumen"
              action={editable && cc?.p !== undefined ? (
                <Button size="small" startIcon={<EditOutlined />} onClick={() => setDlg({ action: 'override', field: 'progres_disetujui', value: String(Number(cv.p) * 100) })}>
                  Ubah progres disetujui
                </Button>) : undefined}>
              <Paper>
                <Table size="small">
                  <TableBody>
                    {t.fields.map((f: any) => (
                      <TableRow key={f.name} hover selected={focus === f.name} onClick={() => f.boxes.length && setFocus(f.name)}
                        sx={{ cursor: f.boxes.length ? 'pointer' : 'default' }}>
                        <TableCell sx={{ color: 'text.secondary', width: '38%' }}>
                          {FIELD_LABEL[f.name] ?? f.name.replace('line_item_', 'Rincian pekerjaan ')}
                          {f.required && <Typography component="span" variant="caption" sx={{ ml: 0.5 }}>(wajib)</Typography>}
                        </TableCell>
                        <TableCell sx={{ color: f.hot ? C.bad : undefined, fontWeight: 500 }}>
                          {f.override !== null ? (
                            <><s style={{ color: C.muted, fontWeight: 400 }}>{f.value}</s> {f.override}</>
                          ) : f.value ?? <Typography component="span" variant="body2" color="text.secondary">tidak tercantum</Typography>}
                        </TableCell>
                        <TableCell sx={{ width: 120 }}>
                          {f.value !== null && (
                            <Tooltip title={f.grounded ? 'Nilai ditemukan di teks OCR' : 'Nilai tidak ditemukan di teks dokumen'}>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <LinearProgress variant="determinate" value={f.confidence * 100} color={f.confidence >= 0.85 ? 'success' : 'error'}
                                  sx={{ flex: 1, height: 6, borderRadius: 3 }} />
                                <Typography variant="caption">{pct(f.confidence)}</Typography>
                              </Box>
                            </Tooltip>)}
                        </TableCell>
                        <TableCell sx={{ width: 44 }} onClick={(e) => e.stopPropagation()}>
                          {editable && !f.name.startsWith('line_item') && (
                            <IconButton size="small" aria-label={`Ubah ${FIELD_LABEL[f.name]}`}
                              onClick={() => setDlg({ action: 'override', field: f.name, value: f.override ?? f.value ?? '' })}>
                              <EditOutlined fontSize="inherit" />
                            </IconButton>)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Paper>
            </Section>
          )}

          {t.journal.length > 0 && (
            <Section title={t.erp_ref ? 'Jurnal terposting' : 'Jurnal yang akan diposting'}>
              <Paper>
                <Table size="small">
                  <TableHead><TableRow><TableCell>Akun</TableCell><TableCell align="right">Debit</TableCell><TableCell align="right">Kredit</TableCell></TableRow></TableHead>
                  <TableBody>
                    {t.journal.map((l: any, i: number) => (
                      <TableRow key={i}>
                        <TableCell sx={{ pl: l.side === 'C' ? 4 : 1.5 }}>{l.account}</TableCell>
                        <TableCell align="right">{l.side === 'D' ? rp(l.amount) : ''}</TableCell>
                        <TableCell align="right">{l.side === 'C' ? rp(l.amount) : ''}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Paper>
            </Section>
          )}

          <Section title="Jejak kerja agen">
            <Paper ref={logBox} sx={{ p: 1.5, maxHeight: 280, overflowY: 'auto', bgcolor: '#FAFAFA' }} aria-live="polite">
              {events.length === 0 && <Typography variant="body2" color="text.secondary">Belum ada aktivitas.</Typography>}
              {events.map((e, i) => (
                <Box key={i} sx={{ display: 'flex', gap: 1.5, py: 0.4, fontSize: 13 }}>
                  <Box sx={{ minWidth: 150, color: AGENT_COLOR[e.agent] ?? C.muted, fontWeight: 600 }}>{e.agent}</Box>
                  <Box sx={{ color: e.level === 'error' ? C.bad : e.level === 'warn' ? C.warn : C.ink }}>{e.msg}</Box>
                </Box>
              ))}
              {processing && <LinearProgress sx={{ mt: 1 }} />}
            </Paper>
          </Section>

          {(visibleActions.length > 0 || t.actions.includes('set_contract')) && (
            <Paper sx={{ p: 1.5, position: 'sticky', bottom: 12, display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center',
              boxShadow: '0 2px 6px rgba(60,64,67,.15)' }}>
              {t.actions.includes('set_contract') && !t.contract && (
                <Button variant="outlined" onClick={() => setDlg({ action: 'set_contract', value: '' })}>Pilih kontrak</Button>)}
              <Box sx={{ flex: 1 }} />
              {visibleActions.map((a: string) => (
                <Button key={a} color={ACTION[a].color ?? 'primary'} variant={ACTION[a].variant}
                  onClick={() => (ACTION[a].reason ? setDlg({ action: a }) : run(a))}>
                  {t.status === 'DISPUTE' && a === 'post' ? 'Terima koreksi & posting ke ERP' : ACTION[a].label}
                </Button>
              ))}
            </Paper>
          )}
        </Box>
      </Box>

      <Dialog open={!!dlg} onClose={() => setDlg(null)} fullWidth maxWidth="sm">
        <DialogTitle>
          {dlg?.action === 'override' ? `Ubah ${FIELD_LABEL[dlg.field ?? ''] ?? dlg.field}` :
            dlg?.action === 'set_contract' ? 'Hubungkan ke kontrak' : ACTION[dlg?.action ?? '']?.label}
        </DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, pt: '8px !important' }}>
          {dlg?.action === 'override' && (
            <TextField label="Nilai baru" value={dlg.value} autoFocus
              helperText={dlg.field === 'progres_disetujui' ? 'Tidak boleh melebihi progres klaim maupun progres BAP.' : undefined}
              onChange={(e) => setDlg({ ...dlg, value: e.target.value })} />)}
          {dlg?.action === 'set_contract' && (
            <TextField select label="Kontrak" value={dlg.value} onChange={(e) => setDlg({ ...dlg, value: e.target.value })}>
              {t.contracts.map((c: any) => <MenuItem key={c.id} value={String(c.id)}>{c.no}: {c.name}</MenuItem>)}
            </TextField>)}
          <TextField label="Alasan pertimbangan audit (minimal 10 karakter)" multiline minRows={2} value={reason}
            onChange={(e) => setReason(e.target.value)} autoFocus={dlg?.action !== 'override'} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDlg(null)}>Batal</Button>
          <Button variant="contained" color={ACTION[dlg?.action ?? '']?.color ?? 'primary'} disabled={reason.trim().length < 10}
            onClick={() => dlg && run(dlg.action, dlg.action === 'override' ? { field: dlg.field, value: dlg.value } :
              dlg.action === 'set_contract' ? { contract_id: Number(dlg.value) } : {})}>
            {dlg?.action === 'override' ? 'Simpan & hitung ulang' : dlg?.action === 'set_contract' ? 'Hubungkan' : ACTION[dlg?.action ?? '']?.label}
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar open={!!toast} autoHideDuration={7000} onClose={() => setToast(null)}>
        {toast ? <Alert severity={toast.err ? 'error' : 'success'} onClose={() => setToast(null)}>{toast.msg}</Alert> : undefined}
      </Snackbar>
    </Box>
  )
}
