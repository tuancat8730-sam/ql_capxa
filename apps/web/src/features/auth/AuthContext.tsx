import { useQueryClient } from '@tanstack/react-query'
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, setAccessToken, setSessionExpiredHandler, type User } from '@/lib/api'

type Status = 'loading' | 'anon' | 'authed'

interface AuthValue {
  status: Status
  user: User | null
  login: (email: string, password: string) => Promise<User>
  logout: () => Promise<void>
}

interface TokenOut {
  access_token: string
  user: User
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<Status>('loading')
  const [user, setUser] = useState<User | null>(null)

  const clear = useCallback(() => {
    setAccessToken(null)
    setUser(null)
    setStatus('anon')
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    setSessionExpiredHandler(clear)
    let cancelled = false
    void (async () => {
      const token = await api.refresh()
      if (cancelled) return
      if (!token) return setStatus('anon')
      try {
        const me = await api.get<User>('/auth/me')
        if (cancelled) return
        setUser(me)
        setStatus('authed')
      } catch {
        if (!cancelled) clear()
      }
    })()
    return () => {
      cancelled = true
      setSessionExpiredHandler(null)
    }
  }, [clear])

  const login = useCallback(async (email: string, password: string) => {
    const data = await api.post<TokenOut>('/auth/login', { email, password }, { retryOn401: false })
    setAccessToken(data.access_token)
    setUser(data.user)
    setStatus('authed')
    return data.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout', undefined, { retryOn401: false })
    } finally {
      clear()
    }
  }, [clear])

  const value = useMemo(() => ({ status, user, login, logout }), [status, user, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
