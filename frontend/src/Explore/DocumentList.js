import React, { useEffect } from 'react'

import useApi from '../Api/useApi'
import useFilters from '../Api/useFilters'
import { useSearchStore } from '../App/stores'
import { Flex, Card, Text, Heading } from '../Primitives'
import DocumentItem from './DocumentItem'

function DocumentList() {
  const setCount = useSearchStore((state) => state.setCount)
  const filters = useFilters()

  const { data } = useApi('/Documents', filters)

  useEffect(() => {
    setCount(data.length)
  }, [data, setCount])

  return (
    <Flex column gap={[3, 3, 3, 4]}>
      {data.length === 0 ? (
        <Card p={[3, 4]}>
          <Heading>No results</Heading>
          <Text as="p">Please adjust the search filters.</Text>
        </Card>
      ) : (
        data.map((document) => (
          <DocumentItem key={document.pid} document={document} />
        ))
      )}
    </Flex>
  )
}
export default DocumentList
