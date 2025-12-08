import React, { useRef, useEffect, Suspense } from 'react'
import { ErrorBoundary } from 'react-error-boundary'
import { useLocation } from 'react-router-dom'

import { useQuery } from '../Api/useApi'
import useFilters from '../Api/useFilters'
import ErrorFallback from '../App/ErrorFallback'
import ResultsCount from '../App/ResultsCount'
import Spinner from '../App/Spinner'
import { useSearchStore } from '../App/stores'
import { Flex, Box } from '../Primitives'
import Search from '../Search/Search'
import DocumentList from './DocumentList'
import QueryDebug from './QueryDebug'

function ExplorePage(props) {
  const { isDesktop } = props

  const { search } = useLocation()
  const setSearch = useSearchStore((state) => state.setSearch)
  const ref = useRef()

  const filters = useFilters()
  const query = useQuery('/documents', filters)

  const toggleModal = () => {
    if (ref.current.hasAttribute('open')) {
      document.querySelector('body').style.overflowY = 'visible'
    } else {
      document.querySelector('body').style.overflowY = 'hidden'
    }
  }

  const exitModal = () => {
    ref.current.removeAttribute('open')
    document.querySelector('body').style.overflowY = 'visible'
  }

  useEffect(() => {
    setSearch(search)
  }, [search, setSearch])

  return (
    <>
      <Flex flexDirection={['column', 'column', 'row']} gap={[3, 3, 3, 4]}>
        {isDesktop ? (
          <Box
            as="aside"
            display={['none', 'none', 'block']}
            width={[1, 1, 1 / 4]}
          >
            {isDesktop && <Search isDesktop />}
          </Box>
        ) : (
          <>
            <Flex alignItems="center">
              <Box
                ref={ref}
                as="details"
                sx={{
                  flex: '1 1 0%',
                  display: ['block', 'block', 'none'],
                  width: [1, 1, 1 / 4],
                }}
              >
                <Box
                  as="summary"
                  onClick={() => toggleModal()}
                  sx={{ fontSize: 3, cursor: 'pointer' }}
                >
                  Filters
                </Box>
                <Box
                  sx={{
                    position: 'fixed',
                    top: 'auto',
                    pb: '120px',
                    left: 0,
                    width: '100%',
                    height: '100%',
                    bg: 'background',
                    zIndex: 10,
                    overflowY: 'auto',
                  }}
                  mt={2}
                >
                  <Search exitModal={exitModal} />
                </Box>
              </Box>
            </Flex>
            <Box sx={{ fontSize: 2 }}>
              <ResultsCount />
            </Box>
          </>
        )}
        <Box width={[1, 1, 3 / 4]}>
          <ErrorBoundary FallbackComponent={ErrorFallback} resetKeys={[search]}>
            <Suspense fallback={<Spinner />}>
              <DocumentList />
            </Suspense>
          </ErrorBoundary>
        </Box>
      </Flex>
      <QueryDebug query={JSON.stringify(query)} />
    </>
  )
}

export default ExplorePage
