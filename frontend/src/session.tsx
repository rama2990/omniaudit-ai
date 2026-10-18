import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, getPersonaId, setPersonaId, type Persona } from './api'

type Session = {
  personas: Persona[]
  persona: Persona | null
  spv: string
  setPersona: (id: string) => void
  setSpv: (spv: string) => void
  meta: { mode: string; model: string; erp_fail: boolean; demo_tools: boolean } | null
  refreshMeta: () => void
}

const Ctx = createContext<Session | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [personas, setPersonas] = useState<Persona[]>([])
  const [pid, setPid] = useState(getPersonaId())
  const [spv, setSpv] = useState('')
  const [meta, setMeta] = useState<Session['meta']>(null)
  const persona = personas.find((p) => p.id === pid) ?? null

  const refreshMeta = useCallback(() => {
    api.get('/meta').then(setMeta).catch(() => setMeta(null))
  }, [])

  useEffect(() => {
    api.get<Persona[]>('/personas').then(setPersonas)
    refreshMeta()
  }, [refreshMeta])

  useEffect(() => {
    if (persona) setSpv(persona.role === 'ROLE_CFO_EXEC' ? 'ALL' : persona.spvs[0])
  }, [persona])

  const setPersona = (id: string) => {
    setPersonaId(id)
    setPid(id)
  }

  return (
    <Ctx.Provider value={{ personas, persona, spv, setPersona, setSpv, meta, refreshMeta }}>{children}</Ctx.Provider>
  )
}

export function useSession() {
  const s = useContext(Ctx)
  if (!s) throw new Error('SessionProvider missing')
  return s
}
