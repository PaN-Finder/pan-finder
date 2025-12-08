import { Suspense } from 'react'
import { ErrorBoundary } from 'react-error-boundary'

import Spinner from '../App/Spinner'
import { formatDate } from '../App/helpers'
import { Box } from '../Primitives'
import providers from '../providers.json'
import { Members, Techniques, Parameters } from './Sections'
import Services from './Services'
import Table from './Table'

function DetailView(props) {
  const { pid, keywords, type, releaseDate, provider: providerURL } = props
  const provider =
    providers.find((provider) => providerURL === provider.url) || {}

  const properties = [
    ['Released', releaseDate && formatDate(releaseDate)],
    ['Facility', [provider.name, provider.homepage]],
    ['Type', type],
    ['Keywords', keywords?.length > 0 && keywords.join(' | ')],
  ].filter(([, content]) => content)

  return (
    <Box mt={3} fontSize={1}>
      <Table data={properties} />
      <ErrorBoundary resetKeys={[pid]} fallback={<Box />}>
        <Suspense fallback={<Box />}>
          <Services provider={provider} pid={pid} />
        </Suspense>
      </ErrorBoundary>
      <ErrorBoundary resetKeys={[pid]} fallback={<Box />}>
        <Suspense fallback={<Spinner />}>
          <Members pid={pid} />
        </Suspense>
      </ErrorBoundary>
      <ErrorBoundary resetKeys={[pid]} fallback={<Box />}>
        <Suspense fallback={<Box />}>
          <Techniques pid={pid} />
        </Suspense>
      </ErrorBoundary>
      <ErrorBoundary resetKeys={[pid]} fallback={<Box />}>
        <Suspense fallback={<Box />}>
          <Parameters pid={pid} />
        </Suspense>
      </ErrorBoundary>
    </Box>
  )
}

export default DetailView
