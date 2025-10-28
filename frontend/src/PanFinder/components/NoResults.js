import React from 'react'

import { Box, Text } from '../../Primitives'

function NoResults() {
  return (
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
  )
}

export default NoResults
