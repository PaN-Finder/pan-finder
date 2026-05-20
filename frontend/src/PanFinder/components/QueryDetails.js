import React, { useState } from 'react'
import {
  FiEdit3,
  FiSearch,
  FiX,
  FiChevronDown,
  FiChevronRight,
} from 'react-icons/fi'

import { Box, Text, Button, Flex } from '../../Primitives'

function QueryDetails({ data, onQueryComponentsSearch }) {
  const [isEditing, setIsEditing] = useState(false)
  const [editedQueryComponents, setEditedQueryComponents] = useState('')
  const [error, setError] = useState(null)
  const [isExpanded, setIsExpanded] = useState(false)
  const queryComponents = data?.raw_structured_data

  if (!data || !queryComponents || !data.id) {
    return null
  }

  const handleEditStart = () => {
    setEditedQueryComponents(JSON.stringify(queryComponents, null, 2))
    setError(null)
    setIsEditing(true)
  }

  const handleSearch = () => {
    try {
      const parsedQueryComponents = JSON.parse(editedQueryComponents)
      onQueryComponentsSearch(data.id, parsedQueryComponents)
      setError(null)
      setIsEditing(false)
    } catch (error) {
      setError(
        error.message || 'Please enter valid JSON for the query components.',
      )
    }
  }

  const handleCancel = () => {
    setIsEditing(false)
    setEditedQueryComponents('')
    setError(null)
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
          {queryComponents && (
            <Box>
              <Flex
                sx={{
                  alignItems: 'center',
                  mb: 2,
                  gap: 2,
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
                  Query Components
                </Text>
                {!isEditing && (
                  <Button
                    variant="action"
                    onClick={handleEditStart}
                    sx={{
                      p: 1,
                      ml: 0,
                      fontSize: '12px',
                      color: '#a0aec0',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 1,
                      ':hover': {
                        color: '#e2e8f0',
                      },
                    }}
                    title="Edit query components"
                  >
                    <FiEdit3 size={14} />
                    Edit JSON
                  </Button>
                )}
                {isEditing && (
                  <Text
                    sx={{
                      fontSize: '11px',
                      fontWeight: '600',
                      color: '#68d391',
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                    }}
                  >
                    Editing
                  </Text>
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
                  <>
                    <textarea
                      value={editedQueryComponents}
                      onChange={(e) => setEditedQueryComponents(e.target.value)}
                      aria-label="Edit query components JSON"
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
                    <Flex
                      sx={{
                        justifyContent: 'flex-end',
                        gap: 2,
                        mt: 2,
                      }}
                    >
                      <Button
                        variant="action"
                        onClick={handleCancel}
                        sx={{
                          p: 1,
                          ml: 0,
                          fontSize: '12px',
                          color: '#f56565',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 1,
                          ':hover': {
                            color: '#fc8181',
                          },
                        }}
                        title="Cancel"
                      >
                        <FiX size={14} />
                        Cancel
                      </Button>
                      <Button
                        variant="action"
                        onClick={handleSearch}
                        sx={{
                          p: 1,
                          ml: 0,
                          fontSize: '12px',
                          color: '#48bb78',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 1,
                          ':hover': {
                            color: '#68d391',
                          },
                        }}
                        title="Save query components and search"
                      >
                        <FiSearch size={14} />
                        Save and Search
                      </Button>
                    </Flex>
                  </>
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
                    {JSON.stringify(queryComponents, null, 2)}
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
