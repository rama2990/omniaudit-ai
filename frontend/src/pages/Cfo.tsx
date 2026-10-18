/* eslint-disable @typescript-eslint/no-explicit-any */
import { Alert, Box, Button, LinearProgress, Paper, Snackbar, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, dt, FIELD_LABEL, pct, rp, STATUS } from '../api'
import { SEV, Section, StatusChip } from '../components/bits'
import { C } from '../theme'

const ACTION_LABEL: Record<string, string> = {
  UPLOAD: 'Upload document', PROCESSED: 'Processed by agents', OVERRIDE: 'Override value', SET_CONTRACT: 'Link contract',
  POST: 'Approve & post', POST_ERP: 'Send to ERP', SUBMIT_CFO: 'Send to CFO', CFO_APPROVE: 'CFO approved',
  CFO_REJECT: 'CFO rejected', CFO_UNLOCK: 'CFO unlocked', REJECT: 'Reject', FLAG: 'Flag dispute', RESEND: 'Resend',
  RETRY: 'Reprocess', UPLOAD_CSV: 'Upload bank statement', ALLOCATE: 'Allocate payment', RECALC_CHANGED: 'Recalculation changed',
  CFO_WAIVER_APPROVE: 'CFO approved waiver', CFO_WAIVER_REJECT: 'CFO rejected waiver', SEED: 'Seed data',
  REGEMINI: 'Re-read by Gemini',
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
      await api.post(`/cfo/waiver/${id}`, { approve, reason: approve ? 'Approved by CFO' : 'Does not meet the waiver policy' })
      setToast({ msg: approve ? 'Waiver approved; late fee removed.' : 'Waiver rejected; late fee charged to the buyer.' })
      load()
    } catch (e) {
      setToast({ msg: (e as Error).message, err: true })
    }
  }

  if (!queue) return <LinearProgress />
  return (
    <Box>
      <Typography variant="h1" sx={{ mb: 0.5 }}>CFO room</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>Decisions only you can make, the audit trail, and agent accuracy.</Typography>

      <Section title="Awaiting your decision">
        <Paper>
          <Table size="small">
            <TableHead><TableRow><TableCell>Type</TableCell><TableCell>SPV</TableCell><TableCell>Reference</TableCell>
              <TableCell align="right">Amount</TableCell><TableCell>Reason</TableCell><TableCell>Status</TableCell><TableCell align="right" /></TableRow></TableHead>
            <TableBody>
              {queue.map((q) => (
                <TableRow key={q.kind + q.id}>
                  <TableCell>{q.kind === 'AP' ? 'Bill' : 'Late-fee waiver'}</TableCell>
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
                    {q.kind === 'AP' ? <Button variant="outlined" size="small" onClick={() => nav(`/ap/${q.id}`)}>Review</Button> : (
                      <>
                        <Button size="small" onClick={() => waiver(q.id, true)}>Approve</Button>
                        <Button size="small" color="error" onClick={() => waiver(q.id, false)}>Reject</Button>
                      </>)}
                  </TableCell>
                </TableRow>
              ))}
              {!queue.length && <TableRow><TableCell colSpan={7} sx={{ py: 3, textAlign: 'center', color: 'text.secondary' }}>Nothing is waiting for your decision.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </Paper>
      </Section>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 2fr' }, gap: 2 }}>
        <Section title="Agent read accuracy">
          <Paper>
            <Table size="small">
              <TableHead><TableRow><TableCell>Field</TableCell><TableCell align="right">Documents</TableCell><TableCell align="right">Corrected</TableCell><TableCell align="right">Accuracy</TableCell></TableRow></TableHead>
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
          <Typography variant="caption" color="text.secondary">Accuracy = fields not corrected by a person, divided by all fields read.</Typography>
        </Section>

        <Section title="Audit trail"
          action={<>
            <Button size="small" onClick={() => api.get('/audit/verify').then(setVerify)}>Verify integrity</Button>
            <Button size="small" color="error" onClick={() => api.post('/demo/tamper').then(() => api.get('/audit/verify').then(setVerify))}>
              Simulate tampering
            </Button>
          </>}>
          {verify && (
            <Alert severity={verify.ok ? 'success' : 'error'} sx={{ mb: 1 }}>
              {verify.ok ? `Hash chain intact: ${verify.checked} entries verified.` :
                `Hash chain broken at entry #${verify.broken_at}. Data was changed outside the app.`}
            </Alert>)}
          <Paper sx={{ maxHeight: 460, overflowY: 'auto' }}>
            <Table size="small" stickyHeader>
              <TableHead><TableRow><TableCell>Time</TableCell><TableCell>Actor</TableCell><TableCell>Action</TableCell><TableCell>Object</TableCell><TableCell>Reason</TableCell></TableRow></TableHead>
              <TableBody>
                {log.map((e) => (
                  <TableRow key={e.id} sx={{ bgcolor: verify && !verify.ok && verify.broken_at === e.id ? C.badSoft : undefined }}>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>{dt(e.ts)}</TableCell>
                    <TableCell>{e.actor}</TableCell>
                    <TableCell>{ACTION_LABEL[e.action] ?? e.action}</TableCell>
                    <TableCell>{e.entity === 'termin' ? `Bill #${e.entity_id}` : e.entity === 'receipt' ? (e.entity_id ? `Payment #${e.entity_id}` : 'Bank statement') : e.entity}
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
