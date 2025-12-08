import { FiThumbsUp, FiThumbsDown } from 'react-icons/fi'
import { Box, Text } from '../../../Primitives'

function FeedbackButtons({ feedbackLoading, feedbackStatus, handleFeedback }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
      <Box
        sx={{
          background:
            'linear-gradient(135deg, rgba(36, 114, 179, 0.2) 0%, rgba(100, 110, 177, 0.25) 25%, rgba(187, 70, 119, 0.2) 75%, rgba(12, 15, 22, 0.95) 100%)',
          borderRadius: '8px',
          overflow: 'hidden',
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          p: 2,
        }}
      >
        <Text sx={{ fontSize: '13px', color: '#a0aec0' }}>
          Was this what you were looking for?
        </Text>
        <button
          type="button"
          aria-label="Thumbs up"
          style={{
            background: 'none',
            border: 'none',
            cursor: feedbackLoading ? 'not-allowed' : 'pointer',
            color: feedbackStatus === 'positive' ? '#48bb78' : '#a0aec0',
            fontSize: 18,
            opacity: feedbackLoading ? 0.5 : 1,
            padding: '4px',
            display: 'flex',
            alignItems: 'center',
          }}
          disabled={feedbackLoading}
          onClick={() => handleFeedback('positive')}
        >
          <FiThumbsUp />
        </button>
        <button
          type="button"
          aria-label="Thumbs down"
          style={{
            background: 'none',
            border: 'none',
            cursor: feedbackLoading ? 'not-allowed' : 'pointer',
            color: feedbackStatus === 'negative' ? '#e53e3e' : '#a0aec0',
            fontSize: 18,
            opacity: feedbackLoading ? 0.5 : 1,
            padding: '4px',
            display: 'flex',
            alignItems: 'center',
          }}
          disabled={feedbackLoading}
          onClick={() => handleFeedback('negative')}
        >
          <FiThumbsDown />
        </button>
        {feedbackStatus === 'error' && (
          <Text sx={{ color: '#e53e3e', fontSize: '13px' }}>
            Error submitting feedback
          </Text>
        )}
      </Box>
    </Box>
  )
}

export default FeedbackButtons
