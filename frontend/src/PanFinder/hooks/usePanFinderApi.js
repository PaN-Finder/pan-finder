import { useState, useCallback, useRef, useEffect, useMemo } from 'react'

import { useFeedback } from '../contexts/FeedbackContext'
import { useSession } from '../contexts/SessionContext'
import { createPanFinderApi, createSessionRequest } from './panFinderApi'

const SESSION_ID_REQUIRED_MSG = 'Session ID is required'
const TURNSTILE_ENABLED =
  process.env.REACT_APP_ENABLE_TURNSTILE === 'true' || false

const createProgressEvent = (event, data = null) => ({
  event,
  data,
  timestamp: Date.now(),
})

const isUnauthorizedError = (error) =>
  error.message.includes('HTTP 401') || error.message.includes('Unauthorized')

const usePanFinderApi = () => {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isRephrasing, setIsRephrasing] = useState(false)
  const [streamingSteps, setStreamingSteps] = useState([])
  const [explanation, setExplanation] = useState('')
  const [explanationError, setExplanationError] = useState(null)
  const { setCurrentQueryId } = useFeedback()
  const {
    sessionId,
    invalidateSession,
    createSession: createSessionFromContext,
  } = useSession()
  const controllerRef = useRef(null)

  // Create memoized API instance with current session
  // When Turnstile is disabled, pass null as sessionId (no session required)
  const api = useMemo(() => {
    if (TURNSTILE_ENABLED) {
      return sessionId ? createPanFinderApi(sessionId) : null
    }
    return createPanFinderApi(null)
  }, [sessionId])

  useEffect(
    () => () => {
      controllerRef.current?.abort()
    },
    [],
  )

  const handleEvent = useCallback(
    (event) => {
      if (!['results', 'explanation_chunk'].includes(event.event)) {
        setStreamingSteps((prev) => [...prev, event])
      }
      switch (event.event) {
        case 'results':
          setData(event.data)
          // if there is id in the event.data set it as queryId and context
          if (event.data.id) {
            setCurrentQueryId(event.data.id)
          }
          break
        case 'explanation_started':
          // Reset explanation state when starting
          setExplanation('')
          setExplanationError(null)
          break
        case 'explanation_chunk':
          setStreamingSteps([]) // Clear streaming steps when receiving explanation chunk
          // Append new content to explanation
          if (event.data?.content) {
            setExplanation((prev) => prev + event.data.content)
          }
          break
        case 'explanation_error':
          setExplanationError(
            event.data?.message || 'Failed to generate explanation',
          )
          break
        case 'search_completed':
          setStreamingSteps([]) // Clear streaming steps when search is completed
          break
        case 'error':
          setError(new Error(event.data.message))
          break
        default:
          // Handle other events if necessary
          break
      }
    },
    [setCurrentQueryId],
  )

  const executeSearch = useCallback(
    async (searchFunction, searchArgs, options = {}) => {
      const { resetStreamingSteps = true } = options

      setIsLoading(true)
      setError(null)
      setData(null)
      setCurrentQueryId(null)
      if (resetStreamingSteps) {
        setStreamingSteps([])
      }
      setExplanation('')
      setExplanationError(null)

      if (controllerRef.current) {
        controllerRef.current.abort()
      }
      const controller = new AbortController()
      controllerRef.current = controller

      try {
        if (!api) {
          setIsLoading(false)
          // Only throw error if Turnstile is enabled but no session
          if (TURNSTILE_ENABLED) {
            setError(new Error(SESSION_ID_REQUIRED_MSG))
          }
          return
        }

        await searchFunction(...searchArgs, handleEvent, controller.signal)
      } catch (error_) {
        if (error_.name !== 'AbortError') {
          if (isUnauthorizedError(error_)) {
            invalidateSession()
          } else {
            setError(error_)
          }
          setData(null)
        }
      } finally {
        if (!controller.signal.aborted) {
          // setStreamingSteps([]) // Clear streaming steps after processing
          setIsLoading(false)
        }
        if (controllerRef.current === controller) {
          controllerRef.current = null
        }
      }
    },
    [handleEvent, setCurrentQueryId, invalidateSession, api],
  )

  const search = useCallback(
    async (query, options = {}) => {
      if (!query || typeof query !== 'string' || query.trim() === '') {
        setError(new Error('Query is required and must be a non-empty string'))
        setIsLoading(false)
        return
      }

      await executeSearch(api?.search, [query], options)
    },
    [executeSearch, api],
  )

  const rephraseQuery = useCallback(
    async (query) => {
      if (!query || typeof query !== 'string' || query.trim() === '') {
        setError(new Error('Query is required and must be a non-empty string'))
        setStreamingSteps([])
        return null
      }

      if (!api) {
        if (TURNSTILE_ENABLED) {
          setError(new Error(SESSION_ID_REQUIRED_MSG))
        }
        setStreamingSteps([])
        return null
      }

      setIsRephrasing(true)
      setError(null)
      setData(null)
      setCurrentQueryId(null)
      setExplanation('')
      setExplanationError(null)
      setStreamingSteps([createProgressEvent('rephrasing_started')])

      try {
        const response = await api.rephraseQuery(query)
        return response?.rewritten_query || query
      } catch (error_) {
        if (isUnauthorizedError(error_)) {
          invalidateSession()
        } else {
          setError(error_)
        }
        setStreamingSteps([])
        return null
      } finally {
        setIsRephrasing(false)
      }
    },
    [api, invalidateSession, setCurrentQueryId],
  )

  const createSession = useCallback(
    async (turnstileToken) => {
      if (!turnstileToken || typeof turnstileToken !== 'string') {
        const error = new Error('Valid Turnstile token is required')
        setError(error)
        throw error
      }

      setIsLoading(true)
      setError(null)

      try {
        return await createSessionFromContext(
          createSessionRequest,
          turnstileToken,
        )
      } catch (error_) {
        const sessionError = new Error(
          `Failed to create session: ${error_.message}`,
        )
        setError(sessionError)
        throw sessionError
      } finally {
        setIsLoading(false)
      }
    },
    [createSessionFromContext],
  )

  const searchWithQueryComponents = useCallback(
    async (id, queryComponents, options = {}) => {
      await executeSearch(
        api?.searchWithStructuredData,
        [id, queryComponents],
        options,
      )
    },
    [executeSearch, api],
  )

  const fetchDocumentDetails = useCallback(
    async (doi) => {
      if (!api) {
        setError(new Error(SESSION_ID_REQUIRED_MSG))
        return
      }

      try {
        return await api.fetchDocumentDetails(doi)
      } catch (error_) {
        throw new Error(`Failed to fetch document details: ${error_.message}`)
      }
    },
    [api],
  )

  const fetchRawDocument = useCallback(
    async (doi) => {
      if (!api) {
        setError(new Error(SESSION_ID_REQUIRED_MSG))
        return
      }

      try {
        return await api.fetchRawDocument(doi)
      } catch (error_) {
        if (isUnauthorizedError(error_)) {
          invalidateSession()
        }
        throw new Error(`Failed to fetch raw document: ${error_.message}`)
      }
    },
    [api, invalidateSession],
  )

  const explainDocument = useCallback(
    async (statisticId, doi, onEvent, signal) => {
      if (!api) {
        setError(new Error(SESSION_ID_REQUIRED_MSG))
        return
      }

      try {
        await api.explainDocument(statisticId, doi, onEvent, signal)
      } catch (error_) {
        if (isUnauthorizedError(error_)) {
          invalidateSession()
        }
        throw error_
      }
    },
    [api, invalidateSession],
  )

  const submitFeedback = useCallback(
    async ({ statistic_id, feedback_type, doi }) => {
      try {
        if (!api) {
          setError(new Error(SESSION_ID_REQUIRED_MSG))
          return
        }

        return await api.submitFeedback({
          statistic_id,
          feedback_type,
          doi,
        })
      } catch (error_) {
        if (isUnauthorizedError(error_)) {
          invalidateSession()
        } else {
          setError(error_)
        }
        throw new Error(`Failed to submit feedback: ${error_.message}`)
      }
    },
    [invalidateSession, api],
  )

  const reset = useCallback(() => {
    // Abort any ongoing streaming request
    if (controllerRef.current) {
      controllerRef.current.abort()
      controllerRef.current = null
    }

    setData(null)
    setError(null)
    setIsLoading(false)
    setIsRephrasing(false)
    setStreamingSteps([])
    setCurrentQueryId(null)
    setExplanation('')
    setExplanationError(null)
  }, [setCurrentQueryId])

  return {
    data,
    error,
    isLoading,
    isRephrasing,
    streamingSteps,
    explanation,
    explanationError,
    rephraseQuery,
    search,
    searchWithQueryComponents,
    reset,
    fetchDocumentDetails,
    fetchRawDocument,
    explainDocument,
    submitFeedback,
    createSession,
  }
}

export { usePanFinderApi }
