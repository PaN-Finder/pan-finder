/* eslint-env browser */
import { useState, useEffect, useCallback } from 'react'

const TURNSTILE_SCRIPT_URL =
  'https://challenges.cloudflare.com/turnstile/v0/api.js'

export function useTurnstile() {
  const [turnstile, setTurnstile] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [scriptLoaded, setScriptLoaded] = useState(false)

  useEffect(() => {
    // If Turnstile is already loaded, set it immediately
    if (window.turnstile) {
      setTurnstile(window.turnstile)
      setScriptLoaded(true)
      return
    }

    // Check if script is already being loaded
    const existingScript = document.querySelector(
      `script[src*="challenges.cloudflare.com/turnstile"]`,
    )
    if (existingScript) {
      // Script is already loading, wait for it
      setIsLoading(true)
      const checkTurnstile = () => {
        if (window.turnstile) {
          setTurnstile(window.turnstile)
          setIsLoading(false)
          setScriptLoaded(true)
        } else {
          setTimeout(checkTurnstile, 100)
        }
      }
      checkTurnstile()
      return
    }

    setIsLoading(true)
    setError(null)

    // Generate a unique callback name to avoid conflicts
    const callbackId = `onTurnstileLoad_${Date.now()}_${Math.random()
      .toString(36)
      .slice(2, 11)}`

    // Define the onload callback
    window[callbackId] = () => {
      if (window.turnstile) {
        setTurnstile(window.turnstile)
        setIsLoading(false)
        setScriptLoaded(true)
      }
      // Clean up the callback
      delete window[callbackId]
    }

    // Create and append the script
    const script = document.createElement('script')
    script.src = `${TURNSTILE_SCRIPT_URL}?onload=${callbackId}`
    script.async = true
    script.defer = true

    // Handle script loading errors
    script.addEventListener('error', () => {
      setError(new Error('Failed to load Turnstile script'))
      setIsLoading(false)
      delete window[callbackId]
    })

    document.head.append(script)

    // Cleanup function
    return () => {
      // Clean up the callback if component unmounts before script loads
      if (window[callbackId]) {
        delete window[callbackId]
      }
    }
  }, [])

  const reset = useCallback(() => {
    setError(null)
  }, [])

  const removeWidget = useCallback(
    (containerId) => {
      if (turnstile && containerId) {
        try {
          turnstile.remove(containerId)
        } catch {
          // Widget removal failed, but this is not critical
        }
      }
    },
    [turnstile],
  )

  return {
    turnstile,
    isLoading,
    error,
    scriptLoaded,
    reset,
    removeWidget,
  }
}
