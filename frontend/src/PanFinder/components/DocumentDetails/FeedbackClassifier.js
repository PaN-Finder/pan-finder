import { useState, useRef, useEffect } from 'react'
import { Box, Text } from '../../../Primitives'

const CLASSIFICATION_OPTIONS = [
  { label: 'Match', value: 'Match' },
  { label: 'Relevant', value: 'Relevant' },
  { label: 'Suggested', value: 'Suggested' },
  { label: 'Not relevant', value: 'Not_Relevant' },
]

function FeedbackClassifier({
  feedbackLoading,
  feedbackStatus,
  handleFeedback,
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const selected = CLASSIFICATION_OPTIONS.find(
    (o) => o.value === feedbackStatus,
  )

  return (
    <Box
      sx={{
        my: 2,
        p: 2,
        borderRadius: '6px',
        bg: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.07)',
        width: 'fit-content',
        ml: 'auto',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: 2,
        }}
      >
        <Text sx={{ fontSize: '12px', color: '#718096', flexShrink: 0 }}>
          Is this result
        </Text>

        <Box ref={ref} style={{ position: 'relative' }}>
          <button
            type="button"
            disabled={feedbackLoading}
            onClick={() => setOpen((o) => !o)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: 'rgba(255,255,255,0.05)',
              border: selected
                ? '1px solid rgba(99,179,237,0.4)'
                : '1px solid rgba(255,255,255,0.12)',
              borderRadius: '4px',
              color: selected ? '#90cdf4' : '#718096',
              cursor: feedbackLoading ? 'not-allowed' : 'pointer',
              fontSize: '12px',
              opacity: feedbackLoading ? 0.5 : 1,
              padding: '4px 10px',
              minWidth: '120px',
              justifyContent: 'space-between',
            }}
          >
            <span>{selected ? selected.label : 'Select…'}</span>
            <span style={{ fontSize: '9px', opacity: 0.6 }}>
              {open ? '▲' : '▼'}
            </span>
          </button>

          {open && (
            <Box
              style={{
                position: 'absolute',
                right: 0,
                bottom: 'calc(100% + 4px)',
                minWidth: '140px',
                background: '#1e2533',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '4px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
                zIndex: 100,
                overflow: 'hidden',
              }}
            >
              {CLASSIFICATION_OPTIONS.map(({ label, value }) => {
                const isActive = feedbackStatus === value
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => {
                      handleFeedback(value)
                      setOpen(false)
                    }}
                    style={{
                      display: 'block',
                      width: '100%',
                      textAlign: 'left',
                      background: isActive
                        ? 'rgba(99,179,237,0.15)'
                        : 'transparent',
                      border: 'none',
                      borderBottom: '1px solid rgba(255,255,255,0.05)',
                      color: isActive ? '#90cdf4' : '#a0aec0',
                      cursor: 'pointer',
                      fontSize: '12px',
                      padding: '7px 12px',
                    }}
                  >
                    {label}
                  </button>
                )
              })}
            </Box>
          )}
        </Box>
      </Box>

      {feedbackStatus === 'error' && (
        <Text
          sx={{ color: '#fc8181', fontSize: '11px', mt: 1, textAlign: 'right' }}
        >
          Error submitting feedback
        </Text>
      )}
    </Box>
  )
}

export default FeedbackClassifier
