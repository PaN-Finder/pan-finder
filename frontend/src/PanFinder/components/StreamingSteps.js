import React from 'react'

import { Box, Flex, Text } from '../../Primitives'

function StreamingSteps({ streamingSteps }) {
  if (streamingSteps.length === 0) {
    return null
  }

  return (
    <>
      {streamingSteps.map((step, index) => {
        const isCompleted = index < streamingSteps.length - 1

        return (
          <Flex
            key={`${step.timestamp}-${step.event}`}
            sx={{
              pb: 2,
              alignItems: 'center',
              justifyContent: 'center',
              gap: 2,
              opacity: 0,
              transform: 'translateY(10px)',
              animation: 'fadeInUp 0.2s ease-out forwards',
            }}
          >
            {/* Progress indicator */}
            <Box
              sx={{
                width: '18px',
                height: '18px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '10px',
                flexShrink: 0,
                transition: 'all 0.15s ease',
                ...(isCompleted
                  ? {
                      backgroundColor: '#48bb78',
                      color: 'white',
                      transform: 'scale(1.05)',
                    }
                  : {
                      border: '2px solid transparent',
                      borderTop: '2px solid #48bb78',
                      borderRight: '2px solid #48bb78',
                      backgroundColor: 'transparent',
                      animation: 'spin 1s linear infinite',
                    }),
              }}
            >
              {isCompleted ? '✓' : ''}
            </Box>
            <Text
              sx={{
                fontSize: 1,
                color: '#a0aec0',
                fontFamily: 'monospace',
                mb: 0,
                transition: 'color 0.15s ease',
              }}
            >
              {step.event === 'rephrasing_started' && 'Rephrasing...'}
              {step.event === 'explanation_started' &&
                'Generating explanation...'}
              {step.event === 'analysis_started' && 'Analysis started...'}
              {step.event === 'analysis_completed' && 'Analysis completed'}
              {step.event === 'data_fetching' && 'Fetching data...'}
              {step.event === 'error' && 'Error occurred'}
            </Text>
          </Flex>
        )
      })}
    </>
  )
}

export default StreamingSteps
