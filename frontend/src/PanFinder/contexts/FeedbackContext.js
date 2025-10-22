import React, { createContext, useContext, useState, useCallback } from 'react'

const FeedbackContext = createContext({
  currentQueryId: null,
  setCurrentQueryId: () => {
    /* default no-op */ return null
  },
  feedbacks: {},
  setFeedback: () => {
    /* default no-op */
  },
})

export function FeedbackProvider({ children }) {
  const [currentQueryId, setCurrentQueryId] = useState(null)
  const [feedbacks, setFeedbacks] = useState({})

  const setFeedback = useCallback((queryId, doi, feedback_type) => {
    setFeedbacks((prev) => ({
      ...prev,
      [`${queryId}|${doi}`]: feedback_type,
    }))
  }, [])

  return React.createElement(
    FeedbackContext.Provider,
    {
      value: {
        currentQueryId,
        setCurrentQueryId,
        feedbacks,
        setFeedback,
      },
    },
    children,
  )
}

export const useFeedback = () => {
  const context = useContext(FeedbackContext)
  if (!context) {
    throw new Error('useFeedback must be used within a FeedbackProvider')
  }
  return context
}
