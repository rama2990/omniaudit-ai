import { createTheme } from '@mui/material/styles'

// Google/Material palette: blue for actions, green/yellow/red only for status.
export const C = {
  blue: '#1A73E8',
  blueSoft: '#E8F0FE',
  ink: '#202124',
  muted: '#5F6368',
  outline: '#DADCE0',
  canvas: '#F1F3F4',
  ok: '#188038',
  okSoft: '#E6F4EA',
  warn: '#B06000',
  warnSoft: '#FEF7E0',
  bad: '#C5221F',
  badSoft: '#FCE8E6',
}

export const theme = createTheme({
  palette: {
    primary: { main: C.blue },
    success: { main: C.ok },
    warning: { main: '#E37400' },
    error: { main: C.bad },
    text: { primary: C.ink, secondary: C.muted },
    background: { default: C.canvas, paper: '#FFFFFF' },
    divider: C.outline,
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: '"Roboto Flex Variable", Roboto, system-ui, sans-serif',
    h1: { fontSize: 28, fontWeight: 500, letterSpacing: -0.2 },
    h2: { fontSize: 22, fontWeight: 500 },
    h3: { fontSize: 16, fontWeight: 600 },
    body1: { fontSize: 14 },
    body2: { fontSize: 13 },
    caption: { fontSize: 12 },
    button: { textTransform: 'none', fontWeight: 600, letterSpacing: 0.1 },
  },
  components: {
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { borderRadius: 20 } } },
    MuiPaper: { defaultProps: { elevation: 0 }, styleOverrides: { root: { border: `1px solid ${C.outline}` } } },
    MuiAppBar: { styleOverrides: { root: { border: 0, borderBottom: `1px solid ${C.outline}` } } },
    MuiTableCell: {
      styleOverrides: {
        root: { fontVariantNumeric: 'tabular-nums', borderColor: C.outline, padding: '8px 12px' },
        head: { color: C.muted, fontWeight: 500, fontSize: 12 },
      },
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 500 } } },
  },
})
