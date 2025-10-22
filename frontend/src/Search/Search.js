import { useState } from 'react'

import { Card, Flex, Box, Button } from '../Primitives'
import template from '../filters.json'
import providers from '../providers.json'
import { useQuery, useSetQueryParams } from '../router-utils'
import Autocomplete from './Autocomplete'
import List from './List'
import Numeric from './Numeric'
import Basic from './Text'

const injectProviders = (obj) => ({
  ...obj,
  options: providers.map(({ name, abbr }) => `${abbr}|${name}`),
})

const filterOf = (type) => {
  const types = {
    numbers: Numeric,
    remoteList: Autocomplete,
    list: List,
    text: Basic,
  }
  return types?.[type] || Basic
}

const useStateful = () => {
  const currentParams = Object.fromEntries(useQuery())
  const [state, setState] = useState(currentParams)
  const setParams = useSetQueryParams()

  const applyParams = () => setParams(state)

  const getParam = (id) => {
    const setValue = (value) => setState((state) => ({ ...state, [id]: value }))
    return {
      setValue,
      remove: () => setValue(''),
      isActive: !!state[id],
      value: state[id],
    }
  }
  return {
    getParam,
    applyParams,
  }
}

function Search(props) {
  const { isDesktop, exitModal } = props
  const { getParam, applyParams } = useStateful()

  const filters = template.map((obj) =>
    obj.id === 'facility' ? injectProviders(obj) : obj,
  )

  function Filter({ filter }) {
    const { id, type } = filter

    const statefulParam = getParam(id)

    const FilterComponent = filterOf(type)
    return (
      <FilterComponent
        obj={filter}
        isStateful={!isDesktop}
        statefulParam={statefulParam}
      />
    )
  }

  return (
    <Flex column mx={isDesktop || 3} gap={[3, 3, 3, 4]}>
      <Card>
        <Flex column gap={[3, 2, 3, 4]}>
          <>
            {filters.map((filter) => (
              <Filter filter={filter} key={filter.id} />
            ))}
            {isDesktop || (
              <Box pt={4}>
                <Button
                  sx={{
                    width: '100%',
                  }}
                  onClick={() => {
                    applyParams()
                    exitModal()
                  }}
                >
                  Apply
                </Button>
              </Box>
            )}
          </>
        </Flex>
      </Card>
    </Flex>
  )
}

export default Search
