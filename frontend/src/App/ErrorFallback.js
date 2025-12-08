import React from 'react'

import { Card, Button, Heading, Text } from '../Primitives'

function ErrorFallback(props) {
  const { resetErrorBoundary } = props

  return (
    <Card p={[3, 4]} role="alert">
      <Heading>Something went wrong</Heading>
      <Text as="p" mb={3}>
        Please adjust the search filters or try again.
      </Text>
      <Button type="button" variant="secondary" onClick={resetErrorBoundary}>
        Try again
      </Button>
    </Card>
  )
}

export default ErrorFallback
