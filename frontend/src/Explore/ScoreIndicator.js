import { useState } from 'react'

import { Box } from '../Primitives'

function ScoreIndicator({ score }) {
  const [hintActive, setHintActive] = useState(false)

  return (
    <Box
      sx={{
        position: 'relative',
        width: 96,
        background: 'linear-gradient(to right, #bb4677, #82b8e4)',
        marginLeft: 1,
        overflow: 'hidden',
        zIndex: 0,
      }}
      onPointerEnter={() => setHintActive(true)}
      onPointerLeave={() => setHintActive(false)}
    >
      <Box
        sx={{
          position: 'relative',
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          fontSize: 12,
          color: '#fff',
          background: 'rgba(0, 0, 0, 0.1)',
          zIndex: 1,
          cursor: 'help',
        }}
      >
        {hintActive ? 'Relevancy' : score.toFixed(3)}
      </Box>
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          bottom: 0,
          right: 0,
          width: `${100 - score * 100}%`,
          background: '#404040',
        }}
      />
    </Box>
  )
}

export default ScoreIndicator
