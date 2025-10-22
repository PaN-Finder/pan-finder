import { useState } from 'react'

import { Box, Button, Flex } from '../Primitives'
import CollapsibleJsonNode from '../PanFinder/components/DocumentDetails/CollapsibleJsonNode'

const decode = (query) => JSON.parse(decodeURIComponent(query))

function Debug({ query }) {
  const json = decode(query)
  const [show, setShow] = useState(false)

  return (
    <Flex
      sx={{
        position: 'fixed',
        bottom: 4,
        right: 4,
        maxHeight: '90vh',
        gap: 4,
      }}
    >
      {show && (
        <Box
          sx={{
            overflowY: 'scroll',
            bg: '#1a202c',
            p: 3,
            borderRadius: '8px',
            maxWidth: '600px',
            boxShadow: '0 10px 25px rgba(0, 0, 0, 0.3)',
          }}
        >
          <CollapsibleJsonNode data={json} />
        </Box>
      )}
      <Flex sx={{ alignItems: 'flex-end' }}>
        <Box>
          <Button onClick={() => setShow(!show)}>
            {show ? ' { x }' : '{ ? }'}
          </Button>
        </Box>
      </Flex>
    </Flex>
  )
}

export default Debug
