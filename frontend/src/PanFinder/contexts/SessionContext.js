import React, { createContext, useContext, useState, useCallback } from 'react'

const TURNSTILE_ENABLED =
  process.env.REACT_APP_ENABLE_TURNSTILE === 'true' || false

const SessionContext = createContext({
  sessionId: null,
  sessionCreating: false,
  setSessionId: () => {
    /* default no-op */
  },
  createSession: () => Promise.resolve(),
  invalidateSession: () => {
    /* default no-op */
  },
})

export function SessionProvider({ children }) {
  const [sessionId, setSessionId] = useState(null)
  const [sessionCreating, setSessionCreating] = useState(false)
  const [error, setError] = useState(null)

  const createSession = useCallback(
    async (createSessionFn, token) => {
      // Skip session creation if Turnstile is disabled
      if (!TURNSTILE_ENABLED) {
        return { session_id: null }
      }

      if (!token || typeof token !== 'string') {
        const error = new Error('Valid Turnstile token is required')
        setError(error)
        throw error
      }

      if (sessionId) {
        return { session_id: sessionId } // Already have valid session
      }

      if (sessionCreating) {
        return // Already creating session
      }

      setSessionCreating(true)
      setError(null)

      try {
        const response = await createSessionFn(token)
        if (!response?.session_id) {
          throw new Error('Invalid session response from server')
        }
        setSessionId(response.session_id)
        return response
      } catch (error) {
        setError(error)
        throw error
      } finally {
        setSessionCreating(false)
      }
    },
    [sessionId, sessionCreating],
  )

  const invalidateSession = useCallback(() => {
    setSessionId(null)
    setError(null)
  }, [])

  const contextValue = {
    sessionId,
    sessionCreating,
    error,
    setSessionId,
    createSession,
    invalidateSession,
  }

  return React.createElement(
    SessionContext.Provider,
    { value: contextValue },
    children,
  )
}

export const useSession = () => {
  const context = useContext(SessionContext)
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider')
  }
  return context
}
