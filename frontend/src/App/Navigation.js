import { Box, Flex, NavLink } from '../Primitives'
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
      <NavLink to="/" exact>
        <Box sx={{ height: ['40px', '50px'], py: [1, 0] }}>
          <PanFinderLogo
            showText={true}
            title="PaN-Finder"
            style={{ height: '100%', width: 'auto', display: 'block' }}
          />
        </Box>
      </NavLink>
    </Flex>
  )
}

export default Navigation
