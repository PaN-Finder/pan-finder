import { useMediaQuery } from '@react-hookz/web'
import React from 'react'
import { Route, Switch } from 'react-router-dom'
import { ThemeProvider } from 'styled-components'

import ExplorePage from '../Explore/ExplorePage'
import HomePage from '../Home/HomePage'
import PanFinderPage from '../PanFinder/PanFinderPage'
import { DocumentDataProvider } from '../PanFinder/contexts/DocumentDataContext'
import { FeedbackProvider } from '../PanFinder/contexts/FeedbackContext'
import { SessionProvider } from '../PanFinder/contexts/SessionContext'
import { Box, Flex } from '../Primitives'
import { breakpoints } from '../breakpoints'
import { useTheme } from '../theme'
import Footer from './Footer'
import GlobalStyles from './GlobalStyles'
import Navigation from './Navigation'
import ScrollToTop from './ScrollToTop'

function App() {
  const theme = useTheme()
  const isDesktop = useMediaQuery(`(min-width: ${breakpoints[1]})`)

  return (
    <ThemeProvider theme={theme}>
      <GlobalStyles />

      <Flex column sx={{ minHeight: '100vh' }}>
        <Navigation />

        <Box
          mx={[3, 3, 3, 4]}
          mb={5}
          sx={{ flexGrow: 1, maxWidth: ['none', 'none', 'none', 'none'] }}
        >
          <SessionProvider>
            <Switch>
              <Route exact path="/">
                <ScrollToTop />
                <HomePage />
              </Route>
              <Route exact path="/pan-finder">
                <ScrollToTop />
                <FeedbackProvider>
                  <DocumentDataProvider>
                    <PanFinderPage />
                  </DocumentDataProvider>
                </FeedbackProvider>
              </Route>
              <Route exact path="/search">
                <ExplorePage isDesktop={isDesktop} />
              </Route>
            </Switch>
          </SessionProvider>
        </Box>
        <Footer />
      </Flex>
    </ThemeProvider>
  )
}

export default App
