import React, { createContext, useContext, useState, useCallback } from 'react'

const DocumentDataContext = createContext({
  explanations: {},
  rawDataCache: {},
  documentDetails: {},
  documentDetailsErrors: {},
  explanationErrors: {},
  rawDataErrors: {},
  setExplanation: () => {
    /* default no-op */
  },
  setRawData: () => {
    /* default no-op */
  },
  setDocumentDetails: () => {
    /* default no-op */
  },
  setDocumentDetailsError: () => {
    /* default no-op */
  },
  setExplanationError: () => {
    /* default no-op */
  },
  setRawDataError: () => {
    /* default no-op */
  },
  clearAll: () => {
    /* default no-op */
  },
})

export function DocumentDataProvider({ children }) {
  const [explanations, setExplanations] = useState({})
  const [rawDataCache, setRawDataCache] = useState({})
  const [documentDetails, setDocumentDetailsState] = useState({})
  const [documentDetailsErrors, setDocumentDetailsErrorsState] = useState({})
  const [explanationErrors, setExplanationErrorsState] = useState({})
  const [rawDataErrors, setRawDataErrorsState] = useState({})

  const setExplanation = useCallback((key, content) => {
    setExplanations((prev) => {
      // If content is null, remove the key
      if (content === null) {
        // eslint-disable-next-line no-unused-vars
        const { [key]: _removed, ...rest } = prev
        return rest
      }
      // If content is a function, call it with current value
      if (typeof content === 'function') {
        return {
          ...prev,
          [key]: content(prev[key] || ''),
        }
      }
      return {
        ...prev,
        [key]: content,
      }
    })
  }, [])

  const setRawData = useCallback((doi, data) => {
    setRawDataCache((prev) => {
      // If data is null, remove the key
      if (data === null) {
        // eslint-disable-next-line no-unused-vars
        const { [doi]: _removed, ...rest } = prev
        return rest
      }
      return {
        ...prev,
        [doi]: data,
      }
    })
  }, [])

  const setDocumentDetails = useCallback((doi, details) => {
    setDocumentDetailsState((prev) => {
      // If details is null, remove the key
      if (details === null) {
        // eslint-disable-next-line no-unused-vars
        const { [doi]: _removed, ...rest } = prev
        return rest
      }
      return {
        ...prev,
        [doi]: details,
      }
    })
  }, [])

  const setDocumentDetailsError = useCallback((doi, error) => {
    setDocumentDetailsErrorsState((prev) => ({
      ...prev,
      [doi]: error,
    }))
  }, [])

  const setExplanationError = useCallback((key, error) => {
    setExplanationErrorsState((prev) => ({
      ...prev,
      [key]: error,
    }))
  }, [])

  const setRawDataError = useCallback((doi, error) => {
    setRawDataErrorsState((prev) => ({
      ...prev,
      [doi]: error,
    }))
  }, [])

  const clearAll = useCallback(() => {
    setExplanations({})
    setRawDataCache({})
    setDocumentDetailsState({})
    setDocumentDetailsErrorsState({})
    setExplanationErrorsState({})
    setRawDataErrorsState({})
  }, [])

  return React.createElement(
    DocumentDataContext.Provider,
    {
      value: {
        explanations,
        rawDataCache,
        documentDetails,
        documentDetailsErrors,
        explanationErrors,
        rawDataErrors,
        setExplanation,
        setRawData,
        setDocumentDetails,
        setDocumentDetailsError,
        setExplanationError,
        setRawDataError,
        clearAll,
      },
    },
    children,
  )
}

export const useDocumentData = () => {
  const context = useContext(DocumentDataContext)
  if (!context) {
    throw new Error(
      'useDocumentData must be used within a DocumentDataProvider',
    )
  }
  return context
}
