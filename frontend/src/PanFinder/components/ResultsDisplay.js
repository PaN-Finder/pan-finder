import React, { useEffect, useRef, useMemo } from 'react'
import { Box } from '../../Primitives'
import ExportCSVButton from './ExportCSVButton'
import NoResults from './NoResults'
import ResultsTable from './ResultsTable'

function ResultsDisplay({
  data,
  expandedRows,
  documentDetails,
  loadingDetails,
  handleRowExpand,
}) {
  const lastAutoExpandedId = useRef(null)

  // Separate relevant and weakly relevant results with metadata
  const relevantResults = useMemo(
    () =>
      (data?.relevant_results || []).map((result) => ({
        ...result,
        resultType: 'relevant',
      })),
    [data?.relevant_results],
  )

  const weaklyRelevantResults = useMemo(
    () =>
      (data?.weakly_relevant_results || []).map((result) => ({
        ...result,
        resultType: 'weakly_relevant',
      })),
    [data?.weakly_relevant_results],
  )

  const allResults = useMemo(
    () => [...relevantResults, ...weaklyRelevantResults],
    [relevantResults, weaklyRelevantResults],
  )

  // Automatically expand the first row when new results are loaded
  useEffect(() => {
    if (
      data?.id &&
      data.id !== lastAutoExpandedId.current &&
      relevantResults.length > 0
    ) {
      const firstDoi = relevantResults[0].doi
      if (firstDoi) {
        lastAutoExpandedId.current = data.id
        handleRowExpand(firstDoi)
      }
    }
  }, [data?.id, relevantResults, handleRowExpand])

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

        {/* Relevant Results Table */}
        <ResultsTable
          title="Most Relevant Documents"
          results={relevantResults}
          expandedRows={expandedRows}
          documentDetails={documentDetails}
          loadingDetails={loadingDetails}
          handleRowExpand={handleRowExpand}
          statisticId={data.id}
        />
      </Box>

      {/* Suggested Results Table (Weakly Relevant) */}
      <ResultsTable
        title="Suggested Documents"
        results={weaklyRelevantResults}
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
