import { Box, Typography } from '@mui/material'
import { useEffect, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { C } from '../theme'

pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString()

export type EvidenceBox = { key: string; page: number; bbox: number[]; tone: 'ok' | 'bad'; label: string }
type PageMeta = { n: number; width: number; height: number; type?: string; source?: string }

const PAGE_LABEL: Record<string, string> = {
  INVOICE: 'Invoice', BAP: 'Site inspection report (BAP)', FAKTUR_PAJAK: 'Tax invoice', FOTO_PROGRES: 'Progress photos', LAIN: 'Other',
}

/** Original PDF with highlight boxes at the OCR coordinates. The focused box is scrolled to the center. */
export default function PdfEvidence({ url, pages, boxes, focus, onFocus }: {
  url: string; pages: PageMeta[]; boxes: EvidenceBox[]; focus: string | null; onFocus: (k: string) => void
}) {
  const wrap = useRef<HTMLDivElement>(null)
  const [w, setW] = useState(560)

  useEffect(() => {
    if (!wrap.current) return
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, Math.floor(e.contentRect.width) - 24)))
    ro.observe(wrap.current)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (!focus) return
    const el = wrap.current?.querySelector(`[data-box="${CSS.escape(focus)}"]`)
    el?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' })
  }, [focus])

  return (
    <Box ref={wrap} sx={{ height: '100%', overflowY: 'auto', bgcolor: '#E8EAED', p: 1.5 }}>
      <Document file={url} loading={<Typography sx={{ p: 2 }}>Loading document…</Typography>}
        error={<Typography sx={{ p: 2 }} color="error">The document can't be displayed.</Typography>}>
        {pages.map((pg) => {
          const scale = w / pg.width
          return (
            <Box key={pg.n} sx={{ mb: 2 }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Page {pg.n}{pg.type ? `: ${PAGE_LABEL[pg.type] ?? pg.type}` : ''}
                {pg.source === 'scan' ? ' (scanned, read by local OCR)' : ''}
              </Typography>
              <Box sx={{ position: 'relative', width: w, boxShadow: '0 1px 3px rgba(60,64,67,.3)' }}>
                <Page pageNumber={pg.n} width={w} renderTextLayer={false} renderAnnotationLayer={false} />
                {boxes.filter((b) => b.page === pg.n).map((b) => {
                  const [x0, y0, x1, y1] = b.bbox
                  const active = focus === b.key
                  const col = b.tone === 'bad' ? C.bad : C.ok
                  return (
                    <Box key={b.key + x0} data-box={b.key} role="button" tabIndex={0} aria-label={b.label}
                      title={b.label} onClick={() => onFocus(b.key)}
                      onKeyDown={(e) => e.key === 'Enter' && onFocus(b.key)}
                      sx={{
                        position: 'absolute', left: x0 * scale - 3, top: y0 * scale - 3,
                        width: (x1 - x0) * scale + 6, height: (y1 - y0) * scale + 6, cursor: 'pointer',
                        border: `2px solid ${active ? C.blue : col}`, borderRadius: '4px',
                        bgcolor: active ? 'rgba(26,115,232,.18)' : `${col}1f`,
                        outline: active ? `4px solid rgba(26,115,232,.25)` : 'none',
                        transition: 'outline-color .2s', '&:focus-visible': { outline: `3px solid ${C.blue}` },
                        '@media (prefers-reduced-motion: no-preference)': active ? {
                          animation: 'pulse 1.2s ease-out 2',
                          '@keyframes pulse': { '0%': { outlineWidth: 0 }, '60%': { outlineWidth: 10 }, '100%': { outlineWidth: 4 } },
                        } : {},
                      }} />
                  )
                })}
              </Box>
            </Box>
          )
        })}
      </Document>
    </Box>
  )
}
