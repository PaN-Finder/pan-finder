import { useState, useEffect } from 'react'
import { FiEye } from 'react-icons/fi'
import { Flex, Box, Text, Button } from '../../../Primitives'
import { useDocumentData } from '../../contexts/DocumentDataContext'
import { useFeedback } from '../../contexts/FeedbackContext'
import { usePanFinderApi } from '../../hooks/usePanFinderApi'
import ExplanationDisplay from '../ExplanationDisplay'
import FeedbackButtons from './FeedbackButtons'
import RawDataViewer from './RawDataViewer'

function LoadingRow() {
  return (
    <tr>
      <td colSpan="4" style={{ padding: '16px', textAlign: 'center' }}>
        <Flex sx={{ alignItems: 'center', justifyContent: 'center', gap: 2 }}>
          <Box
            sx={{
              width: '18px',
              height: '18px',
              borderRadius: '50%',
              border: '2px solid transparent',
              borderTop: '2px solid #48bb78',
              borderRight: '2px solid #48bb78',
              backgroundColor: 'transparent',
              flexShrink: 0,
              animation: 'spin 1s linear infinite',
            }}
          />
          <Text sx={{ color: '#a0aec0' }}>Loading document details...</Text>
        </Flex>
      </td>
    </tr>
  )
}

function ErrorRow({ error }) {
  return (
    <tr>
      <td colSpan="4" style={{ padding: '16px' }}>
        <Box sx={{ bg: '#742a2a', p: 3, borderRadius: '4px' }}>
          <Text sx={{ color: '#fed7d7' }}>{error}</Text>
        </Box>
      </td>
    </tr>
  )
}

function DocumentField({ label, children }) {
  return (
    <Box
      sx={{
        mb: 1.5,
      }}
    >
      <Text
        sx={{
          fontSize: '1em',
          fontWeight: 'bold',
          color: '#a0aec0',
        }}
      >
        {label}
      </Text>
      {children}
    </Box>
  )
}

function DocumentDetails({ details, isLoading, doi, statisticId }) {
  const { submitFeedback, fetchRawDocument } = usePanFinderApi()
  const { feedbacks, setFeedback, currentQueryId } = useFeedback()
  const {
    rawDataCache,
    explanations,
    documentDetailsErrors,
    explanationErrors,
    rawDataErrors,
    setRawData,
    setRawDataError,
  } = useDocumentData()
  const [feedbackStatus, setFeedbackStatus] = useState(null)
  const [feedbackLoading, setFeedbackLoading] = useState(false)
  const [rawDataLoading, setRawDataLoading] = useState(false)

  const rawData = details?.doi ? rawDataCache[details.doi] : null

  // Get explanation and errors from context using statisticId and doi
  const explanationKey = `${statisticId}|${doi}`
  const explanation = explanations[explanationKey]
  const explanationError = explanationErrors[explanationKey]
  const documentDetailsError = documentDetailsErrors[doi]
  const rawDataError = rawDataErrors[doi]

  useEffect(() => {
    if (details?.doi && currentQueryId && feedbacks) {
      const stored = feedbacks[`${currentQueryId}|${details.doi}`]
      if (stored === 'positive' || stored === 'negative') {
        setFeedbackStatus(stored)
      } else {
        setFeedbackStatus(null)
      }
    }
  }, [details?.doi, feedbacks, currentQueryId])

  const handleFeedback = async (type) => {
    if (!details?.doi || !currentQueryId) {
      return
    }
    setFeedbackLoading(true)
    setFeedbackStatus(null)
    try {
      await submitFeedback({
        statistic_id: currentQueryId,
        feedback_type: type,
        doi: details.doi,
      })
      setFeedbackStatus(type)
      setFeedback(currentQueryId, details.doi, type)
    } catch {
      setFeedbackStatus('error')
    } finally {
      setFeedbackLoading(false)
    }
  }

  const handleFetchRawData = async () => {
    if (!details?.doi) {
      return
    }
    setRawDataLoading(true)
    // Clear error on retry
    setRawDataError(details.doi, null)
    try {
      const rawResult = await fetchRawDocument(details.doi)
      setRawData(details.doi, rawResult)
      // Clear error on success
      setRawDataError(details.doi, null)
    } catch (error) {
      // Remove from cache so it can be retried
      setRawData(details.doi, null)
      // Show error but allow retry
      setRawDataError(details.doi, error.message)
    } finally {
      setRawDataLoading(false)
    }
  }

  const handleDownloadRawData = () => {
    if (!rawData) return

    const jsonString =
      typeof rawData === 'object'
        ? JSON.stringify(rawData, null, 2)
        : String(rawData)

    const blob = new Blob([jsonString], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `raw-data-${details.doi.replace(/\//g, '-')}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  // Safely stringify and truncate large raw data
  const getRawDataDisplay = () => {
    if (!rawData) return null

    try {
      const jsonString =
        typeof rawData === 'object'
          ? JSON.stringify(rawData, null, 2)
          : String(rawData)

      const maxLength = 50000 // ~50KB limit for display
      if (jsonString.length > maxLength) {
        const truncated = jsonString.slice(0, maxLength)
        return {
          content: truncated,
          isTruncated: true,
          originalLength: jsonString.length,
        }
      }

      return {
        content: jsonString,
        isTruncated: false,
        originalLength: jsonString.length,
      }
    } catch (error) {
      return {
        content: 'Error: Unable to display raw data',
        isTruncated: false,
        originalLength: 0,
      }
    }
  }

  const rawDataDisplay = getRawDataDisplay()

  if (isLoading) {
    return <LoadingRow />
  }
  if (documentDetailsError) {
    return <ErrorRow error={documentDetailsError} />
  }
  if (!details) {
    return null
  }

  return (
    <tr>
      <td
        colSpan="5"
        style={{ padding: 0, backgroundColor: '#1a202c', position: 'relative' }}
      >
        <Box
          sx={{
            p: 4,
            paddingTop: 2,
            paddingBottom: 2,
            borderTop: '1px solid #4a5568',
            position: 'relative',
          }}
        >
          <ExplanationDisplay
            explanation={explanation}
            explanationError={explanationError}
          />
          <FeedbackButtons
            feedbackLoading={feedbackLoading}
            feedbackStatus={feedbackStatus}
            handleFeedback={handleFeedback}
          />
          <Box sx={{ display: 'grid', gap: 2 }}>
            <DocumentField label="DOI">
              <Text
                sx={{
                  color: '#e2e8f0',
                  fontFamily: 'monospace',
                }}
              >
                <a
                  href={`https://doi.org/${details.doi}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    color: '#63b3ed',
                    textDecoration: 'none',
                  }}
                  onMouseOver={(e) => {
                    e.target.style.textDecoration = 'underline'
                  }}
                  onFocus={(e) => {
                    e.target.style.textDecoration = 'underline'
                  }}
                  onMouseOut={(e) => {
                    e.target.style.textDecoration = 'none'
                  }}
                  onBlur={(e) => {
                    e.target.style.textDecoration = 'none'
                  }}
                >
                  {details.doi}
                </a>
              </Text>
            </DocumentField>

            <DocumentField label="Title">
              <Text
                sx={{
                  color: '#e2e8f0',
                }}
              >
                {details.title}
              </Text>
            </DocumentField>

            {details.facility_name && (
              <DocumentField label="Facility">
                <Text sx={{ color: '#e2e8f0' }}>{details.facility_name}</Text>
              </DocumentField>
            )}

            {details.abstract && (
              <DocumentField label="Abstract">
                <Text sx={{ color: '#e2e8f0' }}>{details.abstract}</Text>
              </DocumentField>
            )}

            {!details.raw && !rawData && (
              <Button
                variant="action"
                sx={{
                  p: 1,
                  ml: 0,
                  fontSize: '12px',
                  alignItems: 'center',
                  gap: 2,
                }}
                title="Show Raw Data"
                onClick={handleFetchRawData}
                disabled={rawDataLoading}
              >
                {rawDataLoading ? (
                  <>
                    <Box
                      sx={{
                        width: '14px',
                        height: '14px',
                        borderRadius: '50%',
                        border: '2px solid transparent',
                        borderTop: '2px solid currentColor',
                        borderRight: '2px solid currentColor',
                        animation: 'spin 1s linear infinite',
                      }}
                    />
                    Loading...
                  </>
                ) : (
                  <>
                    <FiEye size={14} />
                    Show Raw Data
                  </>
                )}
              </Button>
            )}
            {rawDataError && (
              <DocumentField label="Raw Data">
                <Box sx={{ bg: '#742a2a', p: 3, borderRadius: '4px' }}>
                  <Text sx={{ color: '#fed7d7', fontSize: '13px' }}>
                    Error loading raw data: {rawDataError}
                  </Text>
                </Box>
              </DocumentField>
            )}
            {rawData && (
              <DocumentField label="Raw Data">
                <RawDataViewer
                  rawData={rawData}
                  rawDataDisplay={rawDataDisplay}
                  onDownload={handleDownloadRawData}
                />
              </DocumentField>
            )}
          </Box>
        </Box>
      </td>
    </tr>
  )
}

export default DocumentDetails
