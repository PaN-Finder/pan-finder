import { Renderer, marked } from 'marked'
import React from 'react'
import { FiAlertCircle } from 'react-icons/fi'

import { Box, Flex, Text } from '../../Primitives'

const renderer = new Renderer()
const linkRenderer = renderer.link
renderer.link = (href, title, text) => {
  const html = linkRenderer.call(renderer, href, title, text)
  return html.replace(/^<a /, '<a target="_blank" rel="nofollow" ')
}

function ExplanationDisplay({ explanation, explanationError }) {
  return (
    <Box
      sx={{
        mt: 1,
        mb: 3,
        width: '100%',
      }}
    >
      <Flex
        sx={{
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 1,
        }}
      >
        <Text sx={{ fontSize: 2, color: '#ccccccff' }}>
          Relevance Explanation
        </Text>
      </Flex>
      <Box
        sx={{
          background:
            'linear-gradient(135deg, rgba(36, 114, 179, 0.3) 0%, rgba(100, 110, 177, 0.4) 25%, rgba(187, 70, 119, 0.3) 75%, rgba(12, 15, 22, 0.9) 100%)',
          borderRadius: '8px',
          overflow: 'hidden',
        }}
      >
        {explanationError ? (
          <Flex
            sx={{
              p: 3,
              alignItems: 'center',
              gap: 2,
              color: '#f56565',
            }}
          >
            <FiAlertCircle size={16} />
            <Text sx={{ fontSize: 1, mb: 0 }}>{explanationError}</Text>
          </Flex>
        ) : (
          <Box sx={{ pt: 0, pr: 3, pb: 0, pl: 3, color: '#ccccccff' }}>
            {explanation && explanation.trim() ? (
              <Text
                sx={{
                  '& *': {
                    color: 'inherit !important',
                    fontSize: '1.1em',
                  },
                  '& h2': {
                    fontSize: '1.2em',
                  },
                }}
                dangerouslySetInnerHTML={{
                  __html: marked(explanation || '', { renderer }),
                }}
              />
            ) : (
              <Text
                sx={{
                  p: 2,
                  color: '#a0aec0',
                  fontStyle: 'italic',
                }}
              >
                Generating explanation...
              </Text>
            )}
          </Box>
        )}
      </Box>
    </Box>
  )
}

export default ExplanationDisplay
