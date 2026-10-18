import { Box, Chip, Tooltip, Typography } from '@mui/material'
import type { ReactNode } from 'react'
import { STATUS, pct } from '../api'
import { C } from '../theme'

const TONE = {
  ok: { bg: C.okSoft, fg: C.ok },
  warn: { bg: C.warnSoft, fg: C.warn },
  bad: { bg: C.badSoft, fg: C.bad },
  info: { bg: C.blueSoft, fg: C.blue },
  mute: { bg: C.canvas, fg: C.muted },
}

export function StatusChip({ status, size = 'small' }: { status: string; size?: 'small' | 'medium' }) {
  const s = STATUS[status] ?? { label: status, tone: 'mute' as const }
  const t = TONE[s.tone]
  return <Chip size={size} label={s.label} sx={{ bgcolor: t.bg, color: t.fg }} />
}

export function ScoreBadge({ score, title }: { score: number; title?: string }) {
  const ok = score >= 0.85
  const t = ok ? TONE.ok : score >= 0.6 ? TONE.warn : TONE.bad
  return (
    <Tooltip title={title ?? (ok ? 'Skor ≥ 85%' : 'Skor di bawah 85%: perlu ditinjau')}>
      <Box
        component="span"
        sx={{ px: 1, py: 0.25, borderRadius: 1, bgcolor: t.bg, color: t.fg, fontWeight: 600, fontSize: 12,
          fontVariantNumeric: 'tabular-nums' }}
      >
        {pct(score)}
      </Box>
    </Tooltip>
  )
}

export const SEV = {
  CRITICAL: { label: 'Kritis', ...TONE.bad },
  HIGH: { label: 'Tinggi', ...TONE.bad },
  MEDIUM: { label: 'Sedang', ...TONE.warn },
  DUP: { label: 'Kemungkinan duplikat', ...TONE.warn },
} as Record<string, { label: string; bg: string; fg: string }>

export function SevDot({ sev }: { sev: string }) {
  const s = SEV[sev]
  return (
    <Tooltip title={s?.label ?? sev}>
      <Box component="span" sx={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', bgcolor: s?.fg, mr: 0.5 }} />
    </Tooltip>
  )
}

export function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <Box sx={{ mb: 2.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1, gap: 1 }}>
        <Typography variant="h3" sx={{ flex: 1 }}>
          {title}
        </Typography>
        {action}
      </Box>
      {children}
    </Box>
  )
}
