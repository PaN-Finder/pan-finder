import { Select } from '@rebass/forms/styled-components'
import { Suspense } from 'react'
import { ErrorBoundary } from 'react-error-boundary'
import { FiSlash } from 'react-icons/fi'

import { Flex, Button } from '../Primitives'
import { useQueryParam } from '../router-utils'
import AsynAutocomplete from './AsyncAutocomplete'
import FilterBox from './Filter'

function Autocomplete(props) {
  const { obj, statefulParam, isStateful } = props
  const queryParam = useQueryParam(obj.id)
  const param = isStateful ? statefulParam : queryParam

  return (
    // eslint-disable-next-line react/jsx-no-useless-fragment
    <ErrorBoundary fallback={<></>}>
      <FilterBox title={obj.display || obj.id} isActive={param.isActive}>
        <Flex sx={{ '& > div:first-child': { flex: '1 1 0%' } }}>
          <Suspense
            fallback={
              <Select>
                <option>Loading...</option>
              </Select>
            }
          >
            <AsynAutocomplete
              obj={obj}
              statefulParam={statefulParam}
              isStateful={isStateful}
            />
          </Suspense>
          <Button
            variant="action"
            disabled={!param.isActive}
            aria-label="Clear"
            onClick={() => param.remove()}
          >
            <FiSlash />
          </Button>
        </Flex>
      </FilterBox>
    </ErrorBoundary>
  )
}

export default Autocomplete
