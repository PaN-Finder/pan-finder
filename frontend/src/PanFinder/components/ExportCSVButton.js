import React from 'react'
import { FiDownload } from 'react-icons/fi'

import { Box } from '../../Primitives'

function getResultLabel(resultType) {
  switch (resultType) {
    case 'matched':
      return 'Matched'
    case 'relevant':
      return 'Relevant'
    case 'weakly_relevant':
      return 'Suggested'
    default:
      return 'Uncategorized'
  }
}

function ExportCSVButton({ results }) {
  const exportToCSV = () => {
    if (!results || results.length === 0) return

    // Define CSV headers
    const headers = ['DOI', 'Title', 'Facility', 'Relevance', 'Overall Score']

    // Convert results to CSV rows
    const rows = results.map((result) => [
      result.doi || '',
      `"${(result.title || '').replace(/"/g, '""')}"`, // Escape quotes in title
      result.facility_name,
      getResultLabel(result.resultType),
      result.overall_score,
    ])

    // Combine headers and rows
    const csvContent = [
      headers.join(','),
      ...rows.map((row) => row.join(',')),
    ].join('\n')

    // Create blob and download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)

    // Generate filename with timestamp
    const timestamp = new Date().toISOString().split('T')[0]
    const filename = `pan-finder-results-${timestamp}.csv`

    link.setAttribute('href', url)
    link.setAttribute('download', filename)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  if (!results || results.length === 0) {
    return null
  }

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      <Box
        as="button"
        onClick={exportToCSV}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 1,
          px: 2,
          py: 1,
          bg: '#1a202c',
          border: '1px solid #4a5568',
          borderRadius: '6px',
          color: '#e2e8f0',
          fontSize: '13px',
          fontWeight: '500',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
          ':hover': {
            bg: '#2d3748',
            borderColor: '#646eb1',
            color: '#e2e8f0',
            transform: 'translateY(-1px)',
            boxShadow: '0 2px 8px rgba(100, 110, 177, 0.3)',
          },
          ':active': {
            transform: 'translateY(0)',
          },
        }}
        title="Export results to CSV"
      >
        <FiDownload size={13} />
        <span>Export</span>
      </Box>
    </Box>
  )
}

export default ExportCSVButton
