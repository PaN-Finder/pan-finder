import React from 'react'

import { Box, Heading } from '../../Primitives'
import ResultTableRow from './ResultTableRow'

const COLORS = {
  heading: '#cccccc',
  border: '#4a5568',
  background: '#2d3748',
  tableHeaderBg: '#1a202c',
  text: '#e2e8f0',
}

const TABLE_HEADER_STYLE = {
  padding: '12px 8px',
  fontWeight: '600',
  fontSize: '13px',
  color: COLORS.text,
}

function ResultsTable({
  title,
  results,
  expandedRows,
  documentDetails,
  loadingDetails,
  handleRowExpand,
  statisticId,
  opacity = 1,
}) {
  if (!results || results.length === 0) {
    return null
  }

  return (
    <Box sx={{ mb: 4 }}>
      <Heading
        sx={{
          color: COLORS.heading,
          fontSize: '17px !important',
        }}
      >
        {title}
      </Heading>
      <Box
        sx={{
          position: 'relative',
          overflowX: 'auto',
          border: '1px solid',
          borderColor: COLORS.border,
          borderRadius: '3px',
          bg: COLORS.background,
          opacity,
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
                borderBottom: `1px solid ${COLORS.border}`,
                backgroundColor: COLORS.tableHeaderBg,
              }}
            >
              <th
                style={{
                  ...TABLE_HEADER_STYLE,
                  textAlign: 'center',
                  width: '40px',
                }}
                aria-label="Expand details"
              ></th>
              <th
                style={{
                  ...TABLE_HEADER_STYLE,
                  textAlign: 'left',
                  width: '150px',
                }}
              >
                DOI
              </th>
              <th
                style={{
                  ...TABLE_HEADER_STYLE,
                  textAlign: 'left',
                  width: 'auto',
                }}
              >
                Title
              </th>
              <th
                style={{
                  ...TABLE_HEADER_STYLE,
                  textAlign: 'center',
                  width: '150px',
                }}
              >
                Facility
              </th>
              <th
                style={{
                  width: '80px',
                }}
                aria-label="Overall Relevance"
              ></th>
            </tr>
          </thead>
          <tbody>
            {results.map((result, index) => (
              <ResultTableRow
                key={result.doi || index}
                result={result}
                index={index}
                onRowClick={handleRowExpand}
                isExpanded={expandedRows.has(result.doi)}
                documentDetails={documentDetails[result.doi]}
                isLoadingDetails={loadingDetails.has(result.doi)}
                resultType={result.resultType}
                statisticId={statisticId}
              />
            ))}
          </tbody>
        </table>
      </Box>
    </Box>
  )
}

export default ResultsTable
