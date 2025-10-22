import React from 'react'

import { Heading, Text, Flex, Box } from '../../Primitives'
import PanFinderLogo from './PanFinderLogo'

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
        <Box
          sx={{
            position: 'relative',
            width: ['100px', '140px', '180px'],
          }}
        >
          <PanFinderLogo
            title="PaN-Finder"
            style={{ width: '100%', height: '100%', display: 'block' }}
          />
        </Box>
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
          <Box
            as="span"
            aria-label="Beta - early preview"
            title="Beta - early preview"
            sx={{
              position: 'absolute',
              top: ['-0.55rem', '-0.5rem', '0rem'],
              right: ['-0.75rem', '-0.85rem', '0rem'],
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '2px',
              fontSize: ['9px', '10px', '11px'],
              lineHeight: 1,
              fontWeight: 'semibold',
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              color: 'textInverted',
              px: ['6px', '7px', '8px'],
              py: ['3px', '3px', '4px'],
              borderRadius: '999px',
              background: (theme) =>
                `linear-gradient(135deg, ${theme.colors.primary} 0%, ${theme.colors.secondary} 45%, ${theme.colors.ternary} 100%)`,
              boxShadow:
                '0 2px 4px rgba(0,0,0,0.25), 0 0 0 1px rgba(255,255,255,0.15), 0 0 10px -2px rgba(100,110,177,0.65)',
              backdropFilter: 'blur(6px)',
              WebkitBackdropFilter: 'blur(6px)',
              cursor: 'default',
              transition: 'transform 0.25s ease, box-shadow 0.25s ease',
              ':hover': {
                transform: 'translateY(-1px) scale(1.06)',
                boxShadow:
                  '0 4px 10px rgba(0,0,0,0.35), 0 0 0 1px rgba(255,255,255,0.25), 0 0 18px -2px rgba(100,110,177,0.85)',
              },
              ':active': { transform: 'translateY(0) scale(0.97)' },
            }}
          >
            BETA
          </Box>
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
