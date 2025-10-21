import React from 'react'

import { Box, Heading, Text } from '../../Primitives'

function ErrorDisplay({ error }) {
  if (!error) {
    return null
  }

  return (
    <Box
      sx={{
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        maxWidth: '600px',
        width: '90%',
        zIndex: 10000,
      }}
    >
      <Box
        sx={{
          p: [3, 4],
          color: 'white',
          borderRadius: '12px',
          border: '1px solid #7c3535ff',
          boxShadow: '0 8px 32px rgba(205, 46, 46, 0.4)',
          backdropFilter: 'blur(10px)',
        }}
        role="alert"
      >
        <Heading as="h3" sx={{ mb: 2, fontSize: 3, fontWeight: 'bold' }}>
          ⚠️ Something went wrong
        </Heading>
        <Text as="p" sx={{ mb: 2, fontSize: 2 }}>
          {error.message}
        </Text>
        <Text as="p" sx={{ fontSize: 1, opacity: 0.9 }}>
          Please try again with a different query or check your connection.
        </Text>
      </Box>
    </Box>
  )
}

export default ErrorDisplay
