import { Input } from '@rebass/forms/styled-components'
import { FiSearch } from 'react-icons/fi'
import { Redirect, Route, useLocation } from 'react-router-dom'

import { Box, Button, Flex, Image, NavLink } from '../Primitives'
import logo from '../logo.svg'
import { useQueryParam } from '../router-utils'
import ResultsCount from './ResultsCount'

function Navigation() {
  const location = useLocation()
  const { value: query, setValue: setQuery } = useQueryParam('q')

  function handleSubmit(evt) {
    evt.preventDefault()
    const param = new URLSearchParams(new FormData(evt.target))
    const newQuery = param.get('q').trim()
    if (newQuery !== '') {
      setQuery(newQuery)
    }
  }

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
        <Box height="logoHeight" p={[1, 0]}>
          <Image height="100%" width="unset" alt="PaNOSC logo" src={logo} />
        </Box>
      </NavLink>

      <NavLink
        to="/pan-finder"
        sx={{
          alignSelf: 'center',
          mx: 3,
          px: 3,
          py: 2,
          background:
            'linear-gradient(135deg, #2472b3 0%, #646eb1 50%, #bb4677 100%)',
          backgroundSize: '200% 200%',
          color: 'rgba(255, 255, 255, 0.95)',
          borderRadius: 3,
          fontSize: 1,
          textTransform: 'none',
          position: 'relative',
          overflow: 'hidden',
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          boxShadow: '0 4px 15px rgba(36, 114, 179, 0.3)',
          animation: 'gradientShift 3s ease infinite',
          '@keyframes gradientShift': {
            '0%': { backgroundPosition: '0% 50%' },
            '50%': { backgroundPosition: '100% 50%' },
            '100%': { backgroundPosition: '0% 50%' },
          },
          ':hover': {
            transform: 'translateY(-2px)',
            boxShadow: '0 8px 25px rgba(36, 114, 179, 0.4)',
            backgroundSize: '300% 300%',
            animation: 'gradientShift 1.5s ease infinite',
          },
          ':active': {
            transform: 'translateY(0)',
            boxShadow: '0 4px 15px rgba(36, 114, 179, 0.3)',
          },
          '::before': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: '-100%',
            width: '100%',
            height: '100%',
            background:
              'linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent)',
            transition: 'left 0.5s',
          },
          ':hover::before': {
            left: '100%',
          },
        }}
      >
        <Flex sx={{ alignItems: 'center', gap: 2 }}>
          <FiSearch size={16} />
          PaN-Finder
        </Flex>
      </NavLink>

      <Route path="/search">
        {!query?.trim() && <Redirect to="/" />}
        <Flex
          as="form"
          sx={{ flex: '1 1 0%', alignItems: 'center', px: 3 }}
          onSubmit={handleSubmit}
        >
          <Flex sx={{ flex: '1 1 0%', maxWidth: '30rem' }}>
            <Input key={location.search} name="q" defaultValue={query} mr={2} />
            <Button aria-label="Search" type="submit">
              <FiSearch />
            </Button>
          </Flex>
          <Box sx={{ display: ['none', 'none', 'inline'], pl: 3 }}>
            <ResultsCount />
          </Box>
        </Flex>
      </Route>
    </Flex>
  )
}

export default Navigation
