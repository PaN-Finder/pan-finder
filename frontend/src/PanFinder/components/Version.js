import React from 'react'

import { Box, Text } from '../../Primitives'

const VERSION = process.env.REACT_APP_VERSION || 'dev'

function Version() {
  if (!VERSION) {
    return null
  }

  return (
    <Box
      sx={{
        mt: 2,
        textAlign: 'center',
      }}
    >
      <Text
        as="span"
        sx={{
          fontSize: 0,
          color: 'text',
          opacity: 0.5,
          fontFamily: 'monospace',
          letterSpacing: '0.05em',
        }}
      >
        {VERSION}
      </Text>
    </Box>
  )
}

export default Version
