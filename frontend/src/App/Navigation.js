import { Link as RouterLink } from 'react-router-dom'

import { Box, Flex } from '../Primitives'
import PanFinderLogo from '../PanFinder/components/PanFinderLogo'

function Navigation() {
  return (
    <Flex
      as="nav"
      sx={{
        position: 'sticky',
        top: 0,
        zIndex: 1,
        height: 'navHeight',
        mb: [3, 4],
        px: [1, 1, 3, 4],
        bg: 'bgNav',
      }}
    >
      <Flex
        as={RouterLink}
        to="/"
        sx={{
          alignItems: 'center',
          px: [2, 3],
          color: 'inherit',
          fontSize: [0, 1],
          fontWeight: 'semibold',
          textDecoration: 'none',
          textTransform: 'uppercase',
          ':hover': { color: 'text', bg: 'background' },
        }}
      >
        <Box sx={{ height: ['40px', '50px'], py: [1, 0] }}>
          <PanFinderLogo
            showText={true}
            title="PaN-Finder"
            style={{ height: '100%', width: 'auto', display: 'block' }}
          />
        </Box>
      </Flex>
    </Flex>
  )
}

export default Navigation
