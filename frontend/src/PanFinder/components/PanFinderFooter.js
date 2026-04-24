import React from 'react'

import { Box, Text, Flex } from '../../Primitives'
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
      }}
    >
      <Box
        sx={{
          position: 'relative',
          background: (theme) =>
            `linear-gradient(135deg, ${theme.colors.primary}15 0%, ${theme.colors.secondary}10 50%, ${theme.colors.ternary}15 100%)`,
          borderRadius: '16px',
          border: '1px solid',
          borderColor: 'rgba(100, 110, 177, 0.2)',
          backdropFilter: 'blur(10px)',
          WebkitBackdropFilter: 'blur(10px)',
          overflow: 'hidden',
          '::before': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '1px',
            background:
              'linear-gradient(90deg, transparent 0%, #2472b3 20%, #646eb1 50%, #bb4677 80%, transparent 100%)',
            opacity: 0.6,
          },
        }}
      >
        <Flex
          sx={{
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
            px: [3, 3, 3],
            py: [3, 3, 3],
            gap: 3,
          }}
        >
          <Box sx={{ maxWidth: '600px' }}>
            <Text
              as="p"
              sx={{
                m: 0,
                mt: 1,
                fontSize: 1,
                lineHeight: 1.6,
                fontWeight: 'bold',
                color: (theme) => theme.colors.secondary,
              }}
            >
              Please verify the results returned.
            </Text>
          </Box>
        </Flex>
      </Box>
      <Version />
    </Box>
  )
}

export default PanFinderFooter
