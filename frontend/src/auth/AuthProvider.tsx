import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useCallback, useMemo, useState } from 'react'

import { ApiError, apiRequest, tokenStorage } from '../lib/api'
import type { CurrentUser, RegisterData, TokenResponse } from '../lib/types'
import { AuthContext, type AuthContextValue } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [token, setToken] = useState(() => tokenStorage.get())

  const meQuery = useQuery({
    queryKey: ['me', token],
    queryFn: async () => {
      try {
        return await apiRequest<CurrentUser>('/auth/me')
      } catch (error) {
        // Expired or invalid token: forget it, which sends the user to the login page.
        if (error instanceof ApiError && error.status === 401) {
          tokenStorage.clear()
          setToken(null)
          return null
        }
        throw error
      }
    },
    enabled: token !== null,
    retry: false,
    staleTime: 5 * 60 * 1000,
  })

  const saveToken = useCallback((response: TokenResponse) => {
    tokenStorage.set(response.access_token)
    setToken(response.access_token)
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await apiRequest<TokenResponse>('/auth/login', {
        method: 'POST',
        form: { username: email, password },
      })
      saveToken(response)
    },
    [saveToken],
  )

  const register = useCallback(
    async (data: RegisterData) => {
      const response = await apiRequest<TokenResponse>('/auth/register', {
        method: 'POST',
        json: data,
      })
      saveToken(response)
    },
    [saveToken],
  )

  const startDemo = useCallback(async () => {
    const response = await apiRequest<TokenResponse>('/auth/demo', { method: 'POST' })
    saveToken(response)
  }, [saveToken])

  const logout = useCallback(() => {
    tokenStorage.clear()
    setToken(null)
    queryClient.clear()
  }, [queryClient])

  const value = useMemo<AuthContextValue>(
    () => ({
      user: token ? (meQuery.data ?? null) : null,
      isLoading: token !== null && meQuery.isPending,
      login,
      register,
      startDemo,
      logout,
    }),
    [token, meQuery.data, meQuery.isPending, login, register, startDemo, logout],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}
