import React, { useEffect, useRef, useMemo } from 'react'
import { Box } from '../../Primitives'
import ExportCSVButton from './ExportCSVButton'
import NoResults from './NoResults'
import ResultsTable from './ResultsTable'

const MATCH_THRESHOLD = 0.95

function ResultsDisplay({
  data,
  expandedRows,
  documentDetails,
  loadingDetails,
  handleRowExpand,
}) {
  const lastAutoExpandedId = useRef(null)

  const matchedResults = useMemo(
    () =>
      (data?.relevant_results || [])
        .filter((result) => (result.overall_score || 0) >= MATCH_THRESHOLD)
        .map((result) => ({
          ...result,
          resultType: 'matched',
        })),
    [data?.relevant_results],
  )

  const relevantResults = useMemo(
    () =>
      (data?.relevant_results || [])
        .filter((result) => (result.overall_score || 0) < MATCH_THRESHOLD)
        .map((result) => ({
          ...result,
          resultType: 'relevant',
        })),
    [data?.relevant_results],
  )

  const suggestedResults = useMemo(
    () =>
      (data?.weakly_relevant_results || []).map((result) => ({
        ...result,
        resultType: 'weakly_relevant',
      })),
    [data?.weakly_relevant_results],
  )

  const allResults = useMemo(
    () => [...matchedResults, ...relevantResults, ...suggestedResults],
    [matchedResults, relevantResults, suggestedResults],
  )

  // Automatically expand the first row when new results are loaded
  useEffect(() => {
    const firstExpandableResult = matchedResults[0] || relevantResults[0]

    if (
      data?.id &&
      data.id !== lastAutoExpandedId.current &&
      firstExpandableResult
    ) {
      const firstDoi = firstExpandableResult.doi
      if (firstDoi) {
        lastAutoExpandedId.current = data.id
        handleRowExpand(firstDoi)
      }
    }
  }, [data?.id, matchedResults, relevantResults, handleRowExpand])

  if (!data) {
    return null
  }

  return (
    <Box
      sx={{
        animation: 'fadeInUp 0.3s ease-out forwards',
      }}
    >
      <Box sx={{ position: 'relative' }}>
        <Box
          sx={{
            position: 'absolute',
            top: '0px',
            right: 0,
            width: 'auto',
            display: 'flex',
            justifyContent: 'flex-end',
            mb: 0,
          }}
        >
          <ExportCSVButton results={allResults} />
        </Box>

        <ResultsTable
          title="Match"
          results={matchedResults}
          expandedRows={expandedRows}
          documentDetails={documentDetails}
          loadingDetails={loadingDetails}
          handleRowExpand={handleRowExpand}
          statisticId={data.id}
        />

        <ResultsTable
          title="Relevant Documents"
          results={relevantResults}
          expandedRows={expandedRows}
          documentDetails={documentDetails}
          loadingDetails={loadingDetails}
          handleRowExpand={handleRowExpand}
          statisticId={data.id}
        />
      </Box>

      <ResultsTable
        title="Suggested Documents"
        results={suggestedResults}
        expandedRows={expandedRows}
        documentDetails={documentDetails}
        loadingDetails={loadingDetails}
        handleRowExpand={handleRowExpand}
        statisticId={data.id}
      />

      {/* No results found message */}
      {allResults.length === 0 && <NoResults />}
    </Box>
  )
}

export default ResultsDisplay
