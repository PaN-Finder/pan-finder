import { useDebouncedCallback } from '@react-hookz/web'
import { Input } from '@rebass/forms/styled-components'
import { FiSlash } from 'react-icons/fi'

import { Flex, Button } from '../Primitives'
import { useQueryParam } from '../router-utils'
import FilterBox from './Filter'

function TextInput(props) {
  const { obj, isStateful, statefulParam } = props

  const queryParam = useQueryParam(obj.id)
  const param = isStateful ? statefulParam : queryParam

  const handleChange = useDebouncedCallback(
    (val) => param.setValue(val),
    [param],
    1000,
  )

  return (
    <FilterBox title={obj.display || obj.id} isActive={param.isActive}>
      <Flex>
        <Input
          px={2}
          fontSize={0}
          defaultValue={param.value}
          onChange={(evt) => {
            const { value } = evt.target
            handleChange(value)
          }}
        />
        <Button
          variant="action"
          disabled={!param.value}
          aria-label="Clear"
          onClick={() => {
            handleChange('')
          }}
        >
          <FiSlash />
        </Button>
      </Flex>
    </FilterBox>
  )
}

export default TextInput
