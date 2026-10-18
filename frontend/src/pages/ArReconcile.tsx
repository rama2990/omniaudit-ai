/* eslint-disable @typescript-eslint/no-explicit-any */
import ArrowBack from '@mui/icons-material/ArrowBack'
import {
  Alert, Autocomplete, Box, Button, Checkbox, FormControlLabel, IconButton, LinearProgress, MenuItem, Paper, Snackbar,
  Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material'
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, getPersonaId, pct, rp } from '../api'
import { ScoreBadge, Section, StatusChip } from '../components/bits'
import { C } from '../theme'

const date = (s: string) => new Date(s).toLocaleDateString('id-ID', { dateStyle: 'medium' })

function SubScore({ label, v }: { label: string; v: string }) {
  return (
    <Box sx={{ flex: 1 }}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <LinearProgress variant="determinate" value={Number(v) * 100} sx={{ height: 5, borderRadius: 3, my: 0.25 }} />
      <Typography variant="caption">{pct(v)}</Typography>
    </Box>
  )
}

export default function ArReconcile() {
  const { id } = useParams()
  const [r, setR] = useState<any>(null)
  const [unitId, setUnitId] = useState<number | null>(null)
  const [waive, setWaive] = useState(false)
  const [reason, setReason] = useState('Pencairan KPR Bank')
  const [just, setJust] = useState('')
  const [search, setSearch] = useState<any[]>([])
  const [toast, setToast] = useState<{ msg: string; err?: boolean } | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback((uid?: number | null, w = false) => {
    const q = new URLSearchParams()
    if (uid) q.set('unit_id', String(uid))
    if (w) q.set('waive', 'true')
    return api.get(`/ar/receipt/${id}?${q}`).then((d) => { setR(d); setUnitId(d.selected_unit?.id ?? null) })
  }, [id])
  useEffect(() => { load().catch((e) => setToast({ msg: e.message, err: true })) }, [load])

  if (!r) return <LinearProgress />
  const done = r.status === 'ALLOCATED'
  const pv = r.preview
  const late = pv?.lines?.some((l: any) => l.late_days > 0)

  const pick = (uid: number) => { setUnitId(uid); load(uid, waive) }
  const toggleWaive = (w: boolean) => { setWaive(w); load(unitId, w) }
  const confirm = async () => {
    setBusy(true)
    try {
      const d = await api.post(`/ar/receipt/${id}/confirm`, {
        unit_id: unitId, waiver: waive ? { reason, justification: just } : null,
      })
      setR(d)
      setToast({ msg: d.penalty_status === 'MENUNGGU_CFO' ? 'Dialokasikan. Waiver menunggu persetujuan CFO.' :
        'Dialokasikan. Kuitansi dikirim ke WhatsApp dan email pembeli.' })
    } catch (e) {
      setToast({ msg: (e as Error).message, err: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <IconButton component={Link} to="/" aria-label="Kembali ke antrean"><ArrowBack /></IconButton>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h1">{rp(r.amount)} dari {r.sender}</Typography>
          <Typography color="text.secondary">Penerimaan {r.bank} tanggal {date(r.date)}</Typography>
        </Box>
        <StatusChip status={r.status} size="medium" />
      </Box>

      <Paper sx={{ p: 2, mb: 2, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 2 }}>
        {[['Tanggal', date(r.date)], ['Nama pengirim', r.sender], ['Bank', r.bank], ['Nominal', rp(r.amount)],
          ['Berita transfer', r.memo], ['Referensi bank', r.ref || '–'], ['Nomor VA', r.va || '–']].map(([k, v]) => (
          <Box key={k}>
            <Typography variant="caption" color="text.secondary">{k}</Typography>
            <Typography variant="body2" sx={{ fontWeight: 500, wordBreak: 'break-word' }}>{v}</Typography>
          </Box>
        ))}
      </Paper>
      {r.dup_flag && <Alert severity="warning" sx={{ mb: 2 }}>Baris yang identik sudah pernah diunggah. Pastikan ini bukan mutasi ganda sebelum dialokasikan.</Alert>}

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '5fr 7fr' }, gap: 2 }}>
        <Box>
          <Section title={done ? 'Unit tujuan' : 'Rekomendasi unit'}>
            {r.candidates.length === 0 && <Typography color="text.secondary">Tidak ada kandidat. Cari unit secara manual.</Typography>}
            {r.candidates.filter((c: any) => !done || c.unit_id === r.unit_id).map((c: any) => {
              const sel = unitId === c.unit_id
              return (
                <Paper key={c.unit_id} onClick={() => !done && pick(c.unit_id)} role="button" tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && !done && pick(c.unit_id)}
                  sx={{ p: 1.5, mb: 1, cursor: done ? 'default' : 'pointer', borderColor: sel ? C.blue : undefined,
                    borderWidth: sel ? 2 : 1, bgcolor: sel ? C.blueSoft : undefined }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography sx={{ fontWeight: 600, flex: 1 }}>{c.code}: {c.buyer}</Typography>
                    <ScoreBadge score={Number(c.score)} title="Match Score" />
                  </Box>
                  {c.via === 'VA' ? (
                    <Typography variant="body2" color="text.secondary">Cocok persis lewat nomor virtual account.</Typography>
                  ) : (
                    <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
                      <SubScore label="Unit (45%)" v={c.s_unit} />
                      <SubScore label="Nama (35%)" v={c.s_nama} />
                      <SubScore label="Nominal (20%)" v={c.s_nominal} />
                    </Box>
                  )}
                </Paper>
              )
            })}
          </Section>
          {!done && r.can_confirm && (
            <Section title="Cari unit lain">
              <Autocomplete options={search} getOptionLabel={(o: any) => `${o.code}: ${o.buyer}`}
                onInputChange={(_, q) => api.get(`/ar/units?spv=${r.spv_id}&q=${encodeURIComponent(q)}`).then(setSearch)}
                onChange={(_, o: any) => o && pick(o.id)}
                renderInput={(p) => <TextField {...p} size="small" placeholder="Kode unit, nama pembeli, atau nomor VA" />} />
            </Section>
          )}
          {r.selected_unit && (
            <Typography variant="body2" color="text.secondary">
              {r.selected_unit.buyer}, VA {r.selected_unit.va}, {r.selected_unit.phone}, {r.selected_unit.email}
            </Typography>
          )}
        </Box>

        <Box>
          {pv && (
            <Section title={done ? 'Alokasi' : 'Pratinjau alokasi & denda angsuran'}>
              <Paper>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Angsuran</TableCell><TableCell>Jatuh tempo</TableCell><TableCell align="right">Hari telat</TableCell>
                      <TableCell align="right">Pokok dibayar</TableCell><TableCell align="right">Denda (1‰/hari)</TableCell>
                      <TableCell align="right">Denda dibayar</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {pv.lines.map((l: any) => (
                      <TableRow key={l.inst_id}>
                        <TableCell>ke-{l.seq}{!l.settled && <Typography component="span" variant="caption" color="text.secondary"> (sebagian)</Typography>}</TableCell>
                        <TableCell>{date(l.due)}</TableCell>
                        <TableCell align="right" sx={{ color: l.late_days ? C.bad : undefined }}>{l.late_days}</TableCell>
                        <TableCell align="right">{rp(l.pokok)}</TableCell>
                        <TableCell align="right">{rp(l.denda)}</TableCell>
                        <TableCell align="right">{rp(l.denda_dibayar)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <Box sx={{ p: 1.5, display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                  <Typography variant="body2">Total denda: <b>{rp(pv.total_denda)}</b>{pv.waived ? ' (dihapus)' : ''}</Typography>
                  {Number(pv.selisih_transfer) > 0 && <Typography variant="body2">Selisih biaya transfer: <b>{rp(pv.selisih_transfer)}</b> (dianggap lunas, toleransi Rp250.000)</Typography>}
                  {Number(pv.titipan) > 0 && <Typography variant="body2">Titipan pembeli: <b>{rp(pv.titipan)}</b></Typography>}
                </Box>
              </Paper>
            </Section>
          )}

          {!done && r.can_confirm && unitId && (
            <Paper sx={{ p: 2 }}>
              {late && (
                <>
                  <FormControlLabel control={<Checkbox checked={waive} onChange={(e) => toggleWaive(e.target.checked)} />}
                    label="Hapus denda keterlambatan (waiver)" />
                  {waive && (
                    <Box sx={{ display: 'grid', gap: 1.5, mt: 1, mb: 2 }}>
                      <TextField select size="small" label="Alasan waiver" value={reason} onChange={(e) => setReason(e.target.value)}
                        helperText={reason === 'Kewenangan Eksekutif' ? 'Alasan ini membutuhkan persetujuan CFO; pokok tetap dialokasikan sekarang.' : undefined}>
                        {r.waiver_reasons.map((w: string) => <MenuItem key={w} value={w}>{w}</MenuItem>)}
                      </TextField>
                      <TextField size="small" label="Justifikasi" multiline minRows={2} value={just} onChange={(e) => setJust(e.target.value)} />
                    </Box>
                  )}
                </>
              )}
              <Button variant="contained" fullWidth disabled={busy || (waive && !just.trim())} onClick={confirm}>
                Konfirmasi alokasi & kirim notifikasi ke pembeli
              </Button>
            </Paper>
          )}

          {done && (
            <Section title="Notifikasi ke pembeli">
              {r.penalty_status === 'MENUNGGU_CFO' && <Alert severity="info" sx={{ mb: 1 }}>Waiver denda menunggu keputusan CFO.</Alert>}
              {r.waiver?.reason && <Typography variant="body2" sx={{ mb: 1 }}>Waiver: {r.waiver.reason}. {r.waiver.justification}</Typography>}
              {r.erp_ref && <Typography variant="body2" sx={{ mb: 1 }}>Jurnal penerimaan terposting dengan nomor batch {r.erp_ref}.</Typography>}
              {r.outbox.map((o: any) => (
                <Paper key={o.id} sx={{ p: 1.5, mb: 1 }}>
                  <Typography variant="caption" color="text.secondary">{o.channel === 'WHATSAPP' ? 'WhatsApp' : 'Email'} ke {o.to}</Typography>
                  <Typography variant="body2" sx={{ my: 0.5 }}>{o.body}</Typography>
                  <Button size="small" href={`/api/outbox/${o.id}/attachment?persona=${getPersonaId()}`} target="_blank">Lihat kuitansi</Button>
                </Paper>
              ))}
            </Section>
          )}
        </Box>
      </Box>
      <Snackbar open={!!toast} autoHideDuration={6000} onClose={() => setToast(null)}>
        {toast ? <Alert severity={toast.err ? 'error' : 'success'} onClose={() => setToast(null)}>{toast.msg}</Alert> : undefined}
      </Snackbar>
    </Box>
  )
}
