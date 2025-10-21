import React, { useState, useEffect, useRef } from 'react'

import { Box } from '../../Primitives'
import { useSession } from '../contexts/SessionContext'
import { useTurnstile } from '../hooks/useTurnstile'

const TURNSTILE_ENABLED =
  process.env.REACT_APP_ENABLE_TURNSTILE === 'true' || false
const TURNSTILE_SITE_KEY = process.env.REACT_APP_TURNSTILE_SITE_KEY

function TurnstileSessionGate({ children, createSessionApi }) {
  const [token, setToken] = useState(null)
  const [widgetRendered, setWidgetRendered] = useState(false)
  const [widgetError, setWidgetError] = useState(null)
  const [isCreatingSession, setIsCreatingSession] = useState(false)
  const { sessionId, sessionCreating, error: sessionError } = useSession()
  const {
    turnstile,
    isLoading: turnstileLoading,
    error: turnstileError,
    scriptLoaded,
    reset: resetTurnstile,
    removeWidget,
  } = useTurnstile()
  const turnstileRef = useRef(null)
  const widgetIdRef = useRef(null)

  // Handle Turnstile token and create session
  useEffect(() => {
    if (!TURNSTILE_ENABLED) return

    const handleSessionCreation = async () => {
      if (token && !sessionId && !sessionCreating && !isCreatingSession) {
        setIsCreatingSession(true)

        try {
          await createSessionApi(token)
          setToken(null) // Clear token after successful session creation
        } catch {
          resetTurnstile()
          setToken(null)
        } finally {
          setIsCreatingSession(false)
        }
      }
    }

    handleSessionCreation()
  }, [
    token,
    sessionId,
    sessionCreating,
    isCreatingSession,
    createSessionApi,
    resetTurnstile,
  ])

  // Render the managed widget once the script is loaded and when session is invalid
  useEffect(() => {
    if (!TURNSTILE_ENABLED) return

    if (
      turnstile &&
      turnstileRef.current &&
      !sessionId &&
      scriptLoaded &&
      !widgetRendered
    ) {
      // Clear any existing widget first
      if (widgetIdRef.current) {
        removeWidget(widgetIdRef.current)
      }

      turnstileRef.current.innerHTML = ''

      // Render new widget
      const widgetId = turnstile.render(turnstileRef.current, {
        sitekey: TURNSTILE_SITE_KEY,
        callback: (token) => setToken(token),
        'error-callback': (e) => {
          setWidgetError(e)
          setToken(null) // Reset token on error
          resetTurnstile()
        },
      })
      widgetIdRef.current = widgetId
      setWidgetRendered(true)
    }

    if (sessionId && widgetRendered) {
      // Clean up widget when session is active
      if (widgetIdRef.current) {
        removeWidget(widgetIdRef.current)
        widgetIdRef.current = null
      }

      if (turnstileRef.current) {
        turnstileRef.current.innerHTML = ''
      }
      setWidgetRendered(false)
    }
  }, [
    turnstile,
    sessionId,
    scriptLoaded,
    widgetRendered,
    removeWidget,
    resetTurnstile,
  ])

  // Cleanup on unmount
  useEffect(() => {
    if (!TURNSTILE_ENABLED) return

    return () => {
      if (widgetIdRef.current) {
        removeWidget(widgetIdRef.current)
      }
    }
  }, [removeWidget])

  // If Turnstile is disabled, render children directly without verification
  if (!TURNSTILE_ENABLED) {
    return <>{children}</>
  }

  return (
    <Box sx={{ position: 'relative' }}>
      {/* Main content with conditional blur */}
      <Box
        sx={{
          filter: sessionId ? 'none' : 'blur(4px)',
          transition: 'filter 0.3s ease-in-out',
          pointerEvents: sessionId ? 'auto' : 'none',
        }}
      >
        {children}
      </Box>

      {/* Overlay with Turnstile widget when no session */}
      {!sessionId && (
        <Box
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <Box
            sx={{
              backgroundColor: 'background.paper',
              borderRadius: 2,
              p: 4,
              boxShadow: 24,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              minWidth: '400px',
            }}
          >
            <Box sx={{ mb: 2, textAlign: 'center' }}>
              <Box sx={{ fontSize: '1.25rem', fontWeight: 'medium', mb: 1 }}>
                Security Verification Required
              </Box>
              <Box sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                Please complete the security challenge to continue
              </Box>
            </Box>

            {turnstileLoading ? (
              <Box
                sx={{
                  mt: 2,
                  fontSize: '0.875rem',
                  textAlign: 'center',
                }}
              >
                Loading security challenge...
              </Box>
            ) : turnstileError || sessionError || widgetError ? (
              <Box
                sx={{
                  mt: 2,
                  color: '#e53e3e',
                  fontSize: '0.875rem',
                  fontWeight: 'bold',
                }}
              >
                {(turnstileError || widgetError || sessionError)?.message ||
                  'Failed to load security challenge. Please refresh the page.'}
              </Box>
            ) : (
              <div ref={turnstileRef} id="turnstile-widget" />
            )}

            {(sessionCreating || isCreatingSession) && (
              <Box
                sx={{
                  mt: 2,
                  fontSize: '0.875rem',
                  textAlign: 'center',
                }}
              >
                Creating secure session...
              </Box>
            )}
          </Box>
        </Box>
      )}
    </Box>
  )
}

export default TurnstileSessionGate
