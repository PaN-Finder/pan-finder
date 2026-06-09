import React from 'react'

import { Box, Text } from '../../Primitives'
import Version from './Version'

function PanFinderFooter() {
  return (
    <Box
      as="footer"
      sx={{
        mt: 4,
        mb: 0,
        mx: 'auto',
        maxWidth: '900px',
        textAlign: 'center',
      }}
    >
      <Text
        sx={{
          fontSize: 0,
          lineHeight: 1.5,
          color: 'text',
          opacity: 0.45,
          letterSpacing: '0.01em',
        }}
      >
        Please verify the results returned.
      </Text>
      <Version />
    </Box>
  )
}

export default PanFinderFooter
