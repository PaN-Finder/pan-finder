import React, { useState } from 'react'
import {
  FiEdit3,
  FiSearch,
  FiX,
  FiChevronDown,
  FiChevronRight,
} from 'react-icons/fi'

import { Box, Text, Button, Flex } from '../../Primitives'

function QueryDetails({ data, onStructuredSearch }) {
  const [isEditing, setIsEditing] = useState(false)
  const [editedData, setEditedData] = useState('')
  const [error, setError] = useState(null)
  const [isExpanded, setIsExpanded] = useState(false)

  if (!data || !data.raw_structured_data || !data.id) {
    return null
  }

  const handleEditStart = () => {
    setEditedData(JSON.stringify(data.raw_structured_data, null, 2))
    setIsEditing(true)
  }

  const handleSearch = () => {
    try {
      const parsedData = JSON.parse(editedData)
      onStructuredSearch(data.id, parsedData)
      setIsEditing(false)
    } catch (error) {
      setError(error.message || 'Please enter valid JSON data.')
    }
  }

  const handleCancel = () => {
    setIsEditing(false)
    setEditedData('')
  }

  return (
    <Box
      sx={{
        mt: 4,
        bg: '#1a202c',
        borderRadius: '3px',
        border: '1px solid #2d3748',
        overflow: 'hidden',
        opacity: 0,
        animation: 'fadeInUp 0.2s ease-out forwards',
        animationDelay: '0.3s',
      }}
    >
      <Box
        onClick={() => setIsExpanded(!isExpanded)}
        sx={{
          padding: '12px 16px',
          fontSize: '13px',
          fontWeight: '500',
          cursor: 'pointer',
          color: '#a0aec0',
          backgroundColor: 'rgba(37, 44, 60, 1)',
          userSelect: 'none',
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        {isExpanded ? (
          <FiChevronDown size={16} style={{ color: '#a0aec0' }} />
        ) : (
          <FiChevronRight size={16} style={{ color: '#a0aec0' }} />
        )}
        Query Details
      </Box>
      {isExpanded && (
        <Box
          sx={{
            p: 3,
          }}
        >
          {data.raw_structured_data && (
            <Box>
              <Flex
                sx={{
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  mb: 2,
                }}
              >
                <Text
                  sx={{
                    fontSize: '12px',
                    fontWeight: '500',
                    color: '#718096',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  Structured Data
                </Text>
                {isEditing ? (
                  <Flex sx={{ gap: 1 }}>
                    <Button
                      variant="action"
                      onClick={handleSearch}
                      sx={{
                        p: 1,
                        ml: 0,
                        fontSize: '12px',
                        color: '#48bb78',
                        ':hover': {
                          color: '#68d391',
                        },
                      }}
                      title="Save and search"
                    >
                      <FiSearch size={14} />
                    </Button>
                    <Button
                      variant="action"
                      onClick={handleCancel}
                      sx={{
                        p: 1,
                        ml: 0,
                        fontSize: '12px',
                        color: '#f56565',
                        ':hover': {
                          color: '#fc8181',
                        },
                      }}
                      title="Cancel"
                    >
                      <FiX size={14} />
                    </Button>
                  </Flex>
                ) : (
                  <Button
                    variant="action"
                    onClick={handleEditStart}
                    sx={{
                      p: 1,
                      ml: 0,
                      fontSize: '12px',
                      color: '#a0aec0',
                      ':hover': {
                        color: '#e2e8f0',
                      },
                    }}
                    title="Edit structured data"
                  >
                    <FiEdit3 size={14} />
                  </Button>
                )}
              </Flex>
              <Box
                sx={{
                  bg: '#111827',
                  p: 2,
                  borderRadius: '2px',
                  border: '1px solid #374151',
                  overflow: 'auto',
                }}
              >
                {error && (
                  <Text
                    sx={{
                      color: '#e53e3e',
                      mb: 2,
                      fontSize: '12px',
                      fontFamily: 'monospace',
                    }}
                  >
                    {error}
                  </Text>
                )}
                {isEditing ? (
                  <textarea
                    value={editedData}
                    onChange={(e) => setEditedData(e.target.value)}
                    aria-label="Edit structured data JSON"
                    style={{
                      width: '100%',
                      minHeight: '200px',
                      padding: '8px',
                      fontSize: '12px',
                      fontFamily: 'monospace',
                      color: '#d1d5db',
                      backgroundColor: '#1f2937',
                      border: '1px solid #374151',
                      borderRadius: '2px',
                      outline: 'none',
                      resize: 'vertical',
                    }}
                  />
                ) : (
                  <pre
                    style={{
                      fontSize: '12px',
                      margin: 0,
                      fontFamily: 'monospace',
                      color: '#d1d5db',
                      lineHeight: 1.4,
                    }}
                  >
                    {JSON.stringify(data.raw_structured_data, null, 2)}
                  </pre>
                )}
              </Box>
            </Box>
          )}
        </Box>
      )}
    </Box>
  )
}

export default QueryDetails
