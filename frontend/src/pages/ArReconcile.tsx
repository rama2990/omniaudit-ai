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

const date = (s: string) => new Date(s).toLocaleDateString('en-GB', { dateStyle: 'medium' })

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
  const [reason, setReason] = useState('')
  const [just, setJust] = useState('')
  const [search, setSearch] = useState<any[]>([])
  const [toast, setToast] = useState<{ msg: string; err?: boolean } | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback((uid?: number | null, w = false) => {
    const q = new URLSearchParams()
    if (uid) q.set('unit_id', String(uid))
    if (w) q.set('waive', 'true')
    return api.get(`/ar/receipt/${id}?${q}`).then((d) => { setR(d); setUnitId(d.selected_unit?.id ?? null); setReason((x) => x || d.waiver_reasons?.[0] || '') })
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
      setToast({ msg: d.penalty_status === 'MENUNGGU_CFO' ? 'Allocated. Waiver awaiting CFO approval.' :
        'Allocated. Receipt sent by WhatsApp and email.' })
    } catch (e) {
      setToast({ msg: (e as Error).message, err: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <IconButton component={Link} to="/" aria-label="Back to queue"><ArrowBack /></IconButton>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h1">{rp(r.amount)} from {r.sender}</Typography>
          <Typography color="text.secondary">{r.bank} payment on {date(r.date)}</Typography>
        </Box>
        <StatusChip status={r.status} size="medium" />
      </Box>

      <Paper sx={{ p: 2, mb: 2, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 2 }}>
        {[['Date', date(r.date)], ['Sender', r.sender], ['Bank', r.bank], ['Amount', rp(r.amount)],
          ['Transfer note', r.memo], ['Bank reference', r.ref || '–'], ['Virtual account', r.va || '–']].map(([k, v]) => (
          <Box key={k}>
            <Typography variant="caption" color="text.secondary">{k}</Typography>
            <Typography variant="body2" sx={{ fontWeight: 500, wordBreak: 'break-word' }}>{v}</Typography>
          </Box>
        ))}
      </Paper>
      {r.dup_flag && <Alert severity="warning" sx={{ mb: 2 }}>An identical row was already uploaded. Make sure this is not a duplicate transaction before allocating it.</Alert>}

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '5fr 7fr' }, gap: 2 }}>
        <Box>
          <Section title={done ? 'Destination unit' : 'Recommended units'}>
            {r.candidates.length === 0 && <Typography color="text.secondary">No candidates. Search for a unit manually.</Typography>}
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
                    <Typography variant="body2" color="text.secondary">Matched exactly by virtual account.</Typography>
                  ) : (
                    <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
                      <SubScore label="Unit (45%)" v={c.s_unit} />
                      <SubScore label="Name (35%)" v={c.s_nama} />
                      <SubScore label="Amount (20%)" v={c.s_nominal} />
                    </Box>
                  )}
                </Paper>
              )
            })}
          </Section>
          {!done && r.can_confirm && (
            <Section title="Find another unit">
              <Autocomplete options={search} getOptionLabel={(o: any) => `${o.code}: ${o.buyer}`}
                onInputChange={(_, q) => api.get(`/ar/units?spv=${r.spv_id}&q=${encodeURIComponent(q)}`).then(setSearch)}
                onChange={(_, o: any) => o && pick(o.id)}
                renderInput={(p) => <TextField {...p} size="small" placeholder="Unit code, buyer name, or VA number" />} />
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
            <Section title={done ? 'Allocation' : 'Allocation preview & late fees'}>
              <Paper>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Installment</TableCell><TableCell>Due date</TableCell><TableCell align="right">Days late</TableCell>
                      <TableCell align="right">Principal paid</TableCell><TableCell align="right">Late fee (0.1%/day)</TableCell>
                      <TableCell align="right">Fee paid</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {pv.lines.map((l: any) => (
                      <TableRow key={l.inst_id}>
                        <TableCell>No. {l.seq}{!l.settled && <Typography component="span" variant="caption" color="text.secondary"> (partial)</Typography>}</TableCell>
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
                  <Typography variant="body2">Total late fee: <b>{rp(pv.total_denda)}</b>{pv.waived ? ' (waived)' : ''}</Typography>
                  {Number(pv.selisih_transfer) > 0 && <Typography variant="body2">Bank fee shortfall: <b>{rp(pv.selisih_transfer)}</b> (treated as paid, IDR 250,000 tolerance)</Typography>}
                  {Number(pv.titipan) > 0 && <Typography variant="body2">Buyer credit: <b>{rp(pv.titipan)}</b></Typography>}
                </Box>
              </Paper>
            </Section>
          )}

          {!done && r.can_confirm && unitId && (
            <Paper sx={{ p: 2 }}>
              {late && (
                <>
                  <FormControlLabel control={<Checkbox checked={waive} onChange={(e) => toggleWaive(e.target.checked)} />}
                    label="Waive late fee" />
                  {waive && (
                    <Box sx={{ display: 'grid', gap: 1.5, mt: 1, mb: 2 }}>
                      <TextField select size="small" label="Waiver reason" value={reason} onChange={(e) => setReason(e.target.value)}
                        helperText={reason === 'Executive authority' ? 'This reason needs CFO approval; the principal is allocated now.' : undefined}>
                        {r.waiver_reasons.map((w: string) => <MenuItem key={w} value={w}>{w}</MenuItem>)}
                      </TextField>
                      <TextField size="small" label="Justification" multiline minRows={2} value={just} onChange={(e) => setJust(e.target.value)} />
                    </Box>
                  )}
                </>
              )}
              <Button variant="contained" fullWidth disabled={busy || (waive && !just.trim())} onClick={confirm}>
                Confirm allocation & notify buyer
              </Button>
            </Paper>
          )}

          {done && (
            <Section title="Buyer notifications">
              {r.penalty_status === 'MENUNGGU_CFO' && <Alert severity="info" sx={{ mb: 1 }}>Late-fee waiver awaiting CFO decision.</Alert>}
              {r.waiver?.reason && <Typography variant="body2" sx={{ mb: 1 }}>Waiver: {r.waiver.reason}. {r.waiver.justification}</Typography>}
              {r.erp_ref && <Typography variant="body2" sx={{ mb: 1 }}>Payment journal posted with batch number {r.erp_ref}.</Typography>}
              {r.outbox.map((o: any) => (
                <Paper key={o.id} sx={{ p: 1.5, mb: 1 }}>
                  <Typography variant="caption" color="text.secondary">{o.channel === 'WHATSAPP' ? 'WhatsApp' : 'Email'} to {o.to}</Typography>
                  <Typography variant="body2" sx={{ my: 0.5 }}>{o.body}</Typography>
                  <Button size="small" href={`/api/outbox/${o.id}/attachment?persona=${getPersonaId()}`} target="_blank">View receipt</Button>
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
