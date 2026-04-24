import React from 'react'

import { Heading, Text, Flex, Box } from '../../Primitives'

function PageHeader() {
  return (
    <>
      <Flex
        sx={{
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: ['column', 'column', 'row'],
          gap: [1, 1, 1],
          mb: 3,
          textAlign: 'center',
        }}
      >
        <Box sx={{ position: 'relative', display: 'inline-block' }}>
          <Heading
            as="h1"
            sx={{
              mb: 0,
              fontSize: [4, 5, 6],
              background:
                'linear-gradient(135deg, #2472b3 0%, #646eb1 50%, #bb4677 100%)',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              color: 'transparent',
              WebkitTextFillColor: 'transparent',
              lineHeight: 1.1,
              letterSpacing: '-0.015em',
              position: 'relative',
              pr: [4, 4, 5],
              '::after': {
                content: '""',
                position: 'absolute',
                left: '40%',
                bottom: '-0.4rem',
                transform: 'translateX(-50%)',
                width: '60%',
                height: '3px',
                borderRadius: '2px',
                background:
                  'linear-gradient(90deg, rgba(36,114,179,0) 0%, #2472b3 15%, #646eb1 50%, #bb4677 85%, rgba(187,70,119,0) 100%)',
                opacity: [0.35, 0.4, 0.5],
              },
            }}
          >
            PaN-Finder
          </Heading>
        </Box>
      </Flex>
      <Text
        as="p"
        sx={{
          textAlign: 'center',
          mb: 4,
          fontSize: [1, 2, 2],
          fontWeight: 'medium',
          opacity: 0.8,
          letterSpacing: '0.025em',
          lineHeight: 1.6,
          maxWidth: '600px',
          mx: 'auto',
        }}
      >
        Search through scientific datasets and research publications
      </Text>
    </>
  )
}

export default PageHeader
