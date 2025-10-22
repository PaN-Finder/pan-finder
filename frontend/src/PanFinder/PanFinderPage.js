import React, { useState } from 'react'

import { Box } from '../Primitives'
import ErrorDisplay from './components/ErrorDisplay'
import FacilitiesSection from './components/FacilitiesSection'
import PanFinderFooter from './components/PanFinderFooter'
import PageHeader from './components/PageHeader'
import QueryDetails from './components/QueryDetails'
import ResultsDisplay from './components/ResultsDisplay'
import SearchForm from './components/SearchForm'
import StreamingSteps from './components/StreamingSteps'
import TurnstileSessionGate from './components/TurnstileSessionGate'
import { useDocumentData } from './contexts/DocumentDataContext'
import { useSession } from './contexts/SessionContext'
import { usePanFinderApi } from './hooks/usePanFinderApi'

function PanFinderPage() {
  const [inputValue, setInputValue] = useState('')
  const [expandedRows, setExpandedRows] = useState(new Set())
  const [loadingDetails, setLoadingDetails] = useState(new Set())
  const { error: sessionError } = useSession()
  const {
    explanations,
    documentDetails,
    setExplanation,
    setDocumentDetails,
    setDocumentDetailsError,
    setExplanationError,
    clearAll: clearDocumentData,
  } = useDocumentData()

  const {
    data,
    error,
    isLoading,
    streamingSteps,
    search,
    searchWithStructuredData,
    fetchDocumentDetails,
    explainDocument,
    createSession: createSessionApi,
    reset,
  } = usePanFinderApi()

  const handleRowExpand = async (doi) => {
    const newExpandedRows = new Set(expandedRows)

    if (expandedRows.has(doi)) {
      // Collapse the row
      newExpandedRows.delete(doi)
      setExpandedRows(newExpandedRows)
    } else {
      // Expand the row
      newExpandedRows.add(doi)
      setExpandedRows(newExpandedRows)

      // Fetch document details if not already loaded
      if (!documentDetails[doi]) {
        const newLoadingDetails = new Set(loadingDetails)
        newLoadingDetails.add(doi)
        setLoadingDetails(newLoadingDetails)

        try {
          const details = await fetchDocumentDetails(doi)
          setDocumentDetails(doi, details)
          // Clear any previous error
          setDocumentDetailsError(doi, null)
        } catch (error_) {
          // Remove from cache so it can be retried
          setDocumentDetails(doi, null)
          // Show error but don't cache in documentDetails - allow retry
          setDocumentDetailsError(
            doi,
            error_.message || 'Failed to load document details',
          )
        } finally {
          const newLoadingDetailsAfter = new Set(loadingDetails)
          newLoadingDetailsAfter.delete(doi)
          setLoadingDetails(newLoadingDetailsAfter)
        }
      }

      // Fetch explanation if not already loaded and we have a statistic ID
      const explanationKey = `${data?.id}|${doi}`
      if (data?.id && !explanations[explanationKey]) {
        setExplanation(explanationKey, ' ')
        setExplanationError(explanationKey, null)

        const controller = new AbortController()

        const handleEvent = (event) => {
          if (event.event === 'explanation_chunk') {
            setExplanation(explanationKey, (current) => {
              if (current === ' ') return event.data?.content || ''
              return current + (event.data?.content || '')
            })
          } else if (event.event === 'error') {
            // Remove from cache so it can be retried
            setExplanation(explanationKey, null)
            // Show error but don't cache in context - stored for display
            setExplanationError(
              explanationKey,
              event.data?.message || 'Failed to generate explanation',
            )
          }
        }

        try {
          await explainDocument(data.id, doi, handleEvent, controller.signal)
        } catch (error_) {
          if (error_.name !== 'AbortError') {
            // Remove from cache so it can be retried
            setExplanation(explanationKey, null)
            // Show error but don't cache in context
            setExplanationError(
              explanationKey,
              error_.message || 'Failed to generate explanation',
            )
          }
        }
      }
    }
  }

  const handleSearch = async () => {
    if (!inputValue.trim()) {
      return
    }

    // Clear previous results state to prepare for new search
    setExpandedRows(new Set())
    setLoadingDetails(new Set())
    clearDocumentData()

    await search(inputValue)
  }

  const handleStructuredSearch = async (id, structuredData) => {
    // Clear previous results state to prepare for new search
    setExpandedRows(new Set())
    setLoadingDetails(new Set())
    clearDocumentData()

    await searchWithStructuredData(id, structuredData)
  }

  function handleSubmit(evt) {
    evt.preventDefault()
    handleSearch()
  }

  function handleInputChange(evt) {
    setInputValue(evt.target.value)
  }

  function handleKeyDown(evt) {
    if (evt.key === 'Enter' && !evt.shiftKey) {
      evt.preventDefault()
      handleSearch()
    }
  }

  function handleClear() {
    setInputValue('')
    setExpandedRows(new Set())
    setLoadingDetails(new Set())
    clearDocumentData()
    reset()
  }

  return (
    <TurnstileSessionGate createSessionApi={createSessionApi}>
      <Box sx={{ maxWidth: '1200px', mx: 'auto' }}>
        <PageHeader />

        <SearchForm
          inputValue={inputValue}
          handleInputChange={handleInputChange}
          handleKeyDown={handleKeyDown}
          handleSubmit={handleSubmit}
          isLoading={isLoading}
          setInputValue={setInputValue}
          handleClear={handleClear}
          hasResults={!!data}
          disabled={false}
        />

        <StreamingSteps streamingSteps={streamingSteps} />
        <ErrorDisplay error={error || sessionError} />
        <ResultsDisplay
          data={data}
          expandedRows={expandedRows}
          documentDetails={documentDetails}
          loadingDetails={loadingDetails}
          handleRowExpand={handleRowExpand}
        />
        <QueryDetails data={data} onStructuredSearch={handleStructuredSearch} />

        <FacilitiesSection only={['ESS', 'ESRF', 'ILL', 'PSI', 'MAXIV']} />
        <PanFinderFooter />
      </Box>
    </TurnstileSessionGate>
  )
}

export default PanFinderPage
