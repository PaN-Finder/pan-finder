import React, { useEffect, useRef, useMemo } from 'react'
import { FiChevronRight } from 'react-icons/fi'

import { Box, Flex, Heading, Text } from '../../Primitives'
import ResultTableRow from './ResultTableRow'
import ExportCSVButton from './ExportCSVButton'

function ResultsDisplay({
  data,
  expandedRows,
  documentDetails,
  loadingDetails,
  handleRowExpand,
}) {
  const lastAutoExpandedId = useRef(null)

  // Combine relevant and weakly relevant results with metadata
  const allResults = useMemo(() => {
    const relevantResults = (data?.relevant_results || []).map((result) => ({
      ...result,
      resultType: 'relevant',
    }))
    const weaklyRelevantResults = (data?.weakly_relevant_results || []).map(
      (result) => ({
        ...result,
        resultType: 'weakly_relevant',
      }),
    )
    return [...relevantResults, ...weaklyRelevantResults]
  }, [data?.relevant_results, data?.weakly_relevant_results])

  const totalResults = data?.total_results || allResults.length
  const resultsToShow = allResults

  // Automatically expand the first row when new results are loaded
  useEffect(() => {
    if (
      data?.id &&
      data.id !== lastAutoExpandedId.current &&
      allResults.length > 0
    ) {
      const firstDoi = allResults[0].doi
      if (firstDoi) {
        lastAutoExpandedId.current = data.id
        handleRowExpand(firstDoi)
      }
    }
  }, [data?.id, allResults, handleRowExpand])

  if (!data) {
    return null
  }

  return (
    <Box
      sx={{
        mt: 3,
        opacity: 0,
        animation: 'fadeInUp 0.3s ease-out forwards',
      }}
    >
      <Flex
        sx={{
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 1,
        }}
      >
        <Heading as="h2" sx={{ m: 0, color: '#ccccccff' }}>
          Most Relevant Documents
        </Heading>
        {totalResults > 0 && (
          <Text
            sx={{
              position: 'absolute',
              left: '50%',
              transform: 'translateX(-50%)',
              fontSize: 0,
              color: '#a0aec0',
              fontStyle: 'italic',
              display: 'flex',
              alignItems: 'center',
              gap: 1,
            }}
          >
            <FiChevronRight size={12} />
            Click rows to view details
          </Text>
        )}
        <Flex sx={{ gap: 2, alignItems: 'center' }}>
          <Text
            sx={{
              fontSize: 1,
              color: 'muted',
              bg: 'muted',
              px: 2,
              py: 1,
              borderRadius: '12px',
              fontWeight: 'medium',
            }}
          >
            {totalResults || 0} total
          </Text>
          <ExportCSVButton results={allResults} />
        </Flex>
      </Flex>
      {allResults && Array.isArray(allResults) && allResults.length > 0 ? (
        <Box
          sx={{
            position: 'relative',
            overflowX: 'auto',
            border: '1px solid',
            borderColor: '#4a5568',
            borderRadius: '3px',
            bg: '#2d3748',
          }}
        >
          <table
            style={{
              width: '100%',
              tableLayout: 'fixed',
              borderCollapse: 'collapse',
              fontSize: '14px',
            }}
          >
            <thead>
              <tr
                style={{
                  borderBottom: '1px solid #4a5568',
                  backgroundColor: '#1a202c',
                }}
              >
                <th
                  style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    fontWeight: '600',
                    fontSize: '13px',
                    color: '#e2e8f0',
                    width: '40px',
                  }}
                >
                  {/* Expand/Collapse column */}
                </th>
                <th
                  style={{
                    padding: '12px 8px',
                    textAlign: 'left',
                    fontWeight: '600',
                    fontSize: '13px',
                    color: '#e2e8f0',
                    width: '150px',
                  }}
                >
                  DOI
                </th>
                <th
                  style={{
                    padding: '12px 8px',
                    textAlign: 'left',
                    fontWeight: '600',
                    fontSize: '13px',
                    color: '#e2e8f0',
                    width: 'auto',
                  }}
                >
                  Title
                </th>
                <th
                  style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    fontWeight: '600',
                    fontSize: '13px',
                    color: '#e2e8f0',
                    width: '150px',
                  }}
                >
                  Facility
                </th>
                <th
                  style={{
                    width: '80px',
                  }}
                ></th>
              </tr>
            </thead>
            <tbody>
              {resultsToShow.map((result, index) => {
                // Add a visual separator between relevant and weakly relevant results
                const showSeparator =
                  index > 0 &&
                  resultsToShow[index - 1]?.resultType === 'relevant' &&
                  result.resultType === 'weakly_relevant'

                return (
                  <React.Fragment key={result.doi || index}>
                    {showSeparator && (
                      <tr>
                        <td colSpan="5" style={{ padding: 0 }}>
                          <div
                            style={{
                              height: '1px',
                              background:
                                'linear-gradient(90deg, transparent 0%, #4a5568 50%, transparent 100%)',
                              margin: '8px 0',
                            }}
                          />
                        </td>
                      </tr>
                    )}
                    <ResultTableRow
                      result={result}
                      index={index}
                      onRowClick={handleRowExpand}
                      isExpanded={expandedRows.has(result.doi)}
                      documentDetails={documentDetails[result.doi]}
                      isLoadingDetails={loadingDetails.has(result.doi)}
                      resultType={result.resultType}
                      statisticId={data.id}
                    />
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>
        </Box>
      ) : (
        <Box
          sx={{
            p: [4, 5],
            bg: 'background',
            borderRadius: '12px',
            textAlign: 'center',
            border: '1px solid',
            borderColor: 'secondary',
            position: 'relative',
            overflow: 'hidden',
            opacity: 0,
            animation: 'fadeInUp 0.3s ease-out forwards',
            animationDelay: '0.15s',
            ':before': {
              content: '""',
              position: 'absolute',
              top: '-2px',
              left: '-2px',
              right: '-2px',
              bottom: '-2px',
              background:
                'linear-gradient(135deg, rgba(36, 114, 179, 0.1) 0%, rgba(100, 110, 177, 0.1) 50%, rgba(187, 70, 119, 0.1) 100%)',
              borderRadius: '12px',
              pointerEvents: 'none',
              zIndex: -1,
            },
          }}
        >
          <Box sx={{ position: 'relative', zIndex: 1 }}>
            {/* Search Icon */}
            <Box
              sx={{
                width: [48, 64],
                height: [48, 64],
                mx: 'auto',
                mb: 3,
                opacity: 0.6,
                filter: 'drop-shadow(0 4px 8px rgba(36, 114, 179, 0.2))',
              }}
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                style={{ width: '100%', height: '100%' }}
              >
                <circle cx="11" cy="11" r="8" />
                <path d="M21 21l-4.35-4.35" />
                <circle cx="11" cy="11" r="3" opacity="0.3" />
              </svg>
            </Box>

            <Text
              sx={{
                fontWeight: 'bold',
                color: 'text',
                fontSize: [3, 4],
                mb: 2,
                lineHeight: 1.2,
                letterSpacing: '-0.02em',
              }}
            >
              No results found
            </Text>

            <Text
              sx={{
                fontSize: [2, 2],
                color: 'text',
                opacity: 0.7,
                lineHeight: 1.5,
                mb: 4,
                maxWidth: '400px',
                mx: 'auto',
              }}
            >
              Your search didn't return any matching documents in our scientific
              database
            </Text>
          </Box>
        </Box>
      )}
    </Box>
  )
}

export default ResultsDisplay
