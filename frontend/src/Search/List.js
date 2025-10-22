import { Select } from '@rebass/forms/styled-components'
import { FiSlash } from 'react-icons/fi'

import { Box, Button, Flex } from '../Primitives'
import { useQueryParam } from '../router-utils'
import FilterBox from './Filter'

function OptionsPicker(props) {
  const { obj, isStateful, statefulParam } = props
  const { id, placeholderOption, display, options: opts } = obj
  const options = opts.map((x) => (x.includes('|') ? x.split('|') : [x, x]))

  const queryParam = useQueryParam(id)
  const param = isStateful ? statefulParam : queryParam

  return (
    <FilterBox title={display || id} isActive={param.isActive}>
      <Flex>
        <Box sx={{ flexGrow: 1 }}>
          <Select
            id={id}
            defaultValue={param.value}
            onChange={(e) => param.setValue(e.target.value)}
          >
            {placeholderOption && (
              <>
                <option key={`${id}-no-option`} value="">
                  {placeholderOption}
                </option>
                <optgroup />
              </>
            )}

            {options.map(([optionValue, optionLabel]) => (
              <option key={optionValue} value={optionValue}>
                {optionLabel}
              </option>
            ))}
          </Select>
        </Box>
        <Button
          sx={{ flexGrow: 0 }}
          variant="action"
          disabled={!param.value}
          aria-label="Clear"
          onClick={() => {
            param.remove()
          }}
        >
          <FiSlash />
        </Button>
      </Flex>
    </FilterBox>
  )
}

export default OptionsPicker
