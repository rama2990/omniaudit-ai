import FactCheckOutlined from '@mui/icons-material/FactCheckOutlined'
import {
  AppBar, Box, Chip, FormControlLabel, Menu, MenuItem, Select, Switch, Tab, Tabs, Toolbar, Tooltip, Typography,
} from '@mui/material'
import { useState } from 'react'
import { Link, Route, Routes, useLocation } from 'react-router-dom'
import { api, ROLE_LABEL } from './api'
import ApReview from './pages/ApReview'
import ArReconcile from './pages/ArReconcile'
import Cfo from './pages/Cfo'
import Dashboard from './pages/Dashboard'
import { useSession } from './session'
import { C } from './theme'

export default function App() {
  const { personas, persona, setPersona, spv, setSpv, meta, refreshMeta } = useSession()
  const loc = useLocation()
  const [demoEl, setDemoEl] = useState<HTMLElement | null>(null)
  const tab = loc.pathname.startsWith('/cfo') ? '/cfo' : '/'

  if (!persona) return <Box sx={{ p: 4 }}>Loading…</Box>
  const isCfo = persona.role === 'ROLE_CFO_EXEC'

  return (
    <Box sx={{ minHeight: '100vh' }}>
      <AppBar position="sticky" color="inherit" elevation={0}>
        <Toolbar sx={{ gap: 2, flexWrap: 'wrap', py: 1 }}>
          <Box component={Link} to="/" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: C.ink, textDecoration: 'none' }}>
            <FactCheckOutlined sx={{ color: C.blue }} />
            <Typography sx={{ fontSize: 20, fontWeight: 500 }}>OmniAudit</Typography>
          </Box>
          <Tabs value={tab} sx={{ minHeight: 40, '& .MuiTab-root': { minHeight: 40 } }}>
            <Tab label="Queue" value="/" component={Link} to="/" />
            {isCfo && <Tab label="CFO room" value="/cfo" component={Link} to="/cfo" />}
          </Tabs>
          <Box sx={{ flex: 1 }} />
          {meta && (
            <Tooltip title={meta.mode === 'gemini' ? `Documents are read by ${meta.model}` :
              'No Gemini API key: fields are read with local text patterns'}>
              <Chip size="small" onClick={(e) => setDemoEl(e.currentTarget)}
                label={meta.mode === 'gemini' ? 'Gemini on' : 'Offline mode'}
                sx={{ bgcolor: meta.mode === 'gemini' ? C.blueSoft : C.warnSoft,
                  color: meta.mode === 'gemini' ? C.blue : C.warn }} />
            </Tooltip>
          )}
          <Menu anchorEl={demoEl} open={!!demoEl} onClose={() => setDemoEl(null)}>
            <MenuItem>
              <FormControlLabel
                control={<Switch checked={!!meta?.erp_fail}
                  onChange={(e) => api.post('/demo/erp_fail', { on: e.target.checked }).then(refreshMeta)} />}
                label="Simulate ERP failure"
              />
            </MenuItem>
          </Menu>
          <Select size="small" value={spv} onChange={(e) => setSpv(e.target.value)} sx={{ minWidth: 200 }}
            aria-label="Select SPV">
            {isCfo && <MenuItem value="ALL">All SPVs</MenuItem>}
            {persona.spvs.map((s) => (
              <MenuItem key={s} value={s}>{persona.spv_names[s]}</MenuItem>
            ))}
          </Select>
          <Select size="small" value={persona.id} onChange={(e) => setPersona(e.target.value)} aria-label="Signed in as"
            renderValue={() => `${persona.name} (${ROLE_LABEL[persona.role]})`} sx={{ minWidth: 220 }}>
            {personas.map((p) => (
              <MenuItem key={p.id} value={p.id}>
                <Box>
                  <Typography>{p.name}</Typography>
                  <Typography variant="caption" color="text.secondary">{p.title}</Typography>
                </Box>
              </MenuItem>
            ))}
          </Select>
        </Toolbar>
      </AppBar>
      <Box component="main" sx={{ p: { xs: 2, md: 3 }, maxWidth: 1600, mx: 'auto' }}>
        <Routes>
          <Route path="/" element={<Dashboard key={persona.id + spv} />} />
          <Route path="/ap/:id" element={<ApReview key={persona.id} />} />
          <Route path="/ar/:id" element={<ArReconcile key={persona.id} />} />
          <Route path="/cfo" element={<Cfo key={persona.id} />} />
        </Routes>
      </Box>
    </Box>
  )
}
