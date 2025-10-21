import { useDebouncedCallback } from '@react-hookz/web'
import { Input, Select } from '@rebass/forms/styled-components'
import { FiSlash } from 'react-icons/fi'

import useFilters, { makeFilter } from '../Api/useFilters'
import { CHAR } from '../App/helpers'
import { Flex, Box, Button } from '../Primitives'
import { useQueryParam } from '../router-utils'
import FilterBox from './Filter'

const stringifyMax = (max, unit) =>
  `${max + CHAR.split}lte${unit ? CHAR.split + unit : ''}`
const stringifyMin = (min, unit) =>
  `${min + CHAR.split}gte${unit ? CHAR.split + unit : ''}`
const stringifyBetween = (min, max, unit) =>
  `${min + CHAR.join + max + CHAR.split}between${unit ? CHAR.split + unit : ''}`

function Numeric({ obj, isStateful, statefulParam }) {
  const { id, display, units = [], defaulUnit: defUnit } = obj
  const { value: stringifiedData } = statefulParam

  const [firstUnit, ...otherUnits] = units
  const defaultUnit = defUnit || firstUnit

  const uriData = useFilters().find((filter) => filter.id === id) || {}
  const statefulData = stringifiedData ? makeFilter(id, stringifiedData) : {}

  const {
    value,
    operator,
    unit = value ? '' : defaultUnit,
  } = isStateful ? statefulData : uriData

  const [min = '', max = ''] = Array.isArray(value)
    ? value
    : operator === 'gte'
    ? [value]
    : [undefined, value]

  const queryParam = useQueryParam(id)
  const param = isStateful ? statefulParam : queryParam
  const { setValue, remove, isActive } = param
  const reset = () => {
    remove()
    return document.querySelector(`#form-${id}`).reset()
  }

  const update = useDebouncedCallback(
    (min, max, unit) => {
      if (min === '' && max === '') {
        return reset()
      }
      if (min && max) {
        return setValue(stringifyBetween(min, max, unit))
      }
      if (max && min === '') {
        return setValue(stringifyMax(max, unit))
      }
      return setValue(stringifyMin(min, unit))
    },
    [setValue, reset],
    1000,
  )

  const defaultUnitVL = defaultUnit.includes('|')
    ? defaultUnit.split('|')
    : [defaultUnit, defaultUnit]
  const otherUnitsVL = otherUnits.map((value) =>
    value.includes('|') ? value.split('|') : [value, value],
  )

  return (
    <FilterBox title={display || id} isActive={isActive}>
      <Box id={`form-${id}`} as="form" onSubmit={(e) => e.preventDefault()}>
        <Flex>
          <Box sx={{ flex: '1 1 0%' }}>
            <Input
              step="any"
              type="number"
              id="min"
              name="min"
              placeholder="min"
              defaultValue={min}
              onChange={(e) => update(e.target.value, max, unit)}
              fontSize={0}
            />
          </Box>
          <Box sx={{ marginLeft: 1, flex: '1 1 0%' }}>
            <Input
              type="number"
              id="max"
              name="max"
              placeholder="max"
              defaultValue={max}
              onChange={(e) => update(min, e.target.value, unit)}
              fontSize={0}
            />
          </Box>
          <Box sx={{ marginLeft: 1, flex: '1 1 0%' }}>
            {units.length > 0 && (
              <Select
                onChange={(e) => {
                  update(min, max, e.target.value)
                }}
                id="unit"
                name="unit"
                defaultValue={unit}
                fontSize={0}
              >
                <option value="">-</option>
                <option value={defaultUnitVL[0]} key={defaultUnitVL[0]}>
                  {defaultUnitVL[1]}
                </option>
                {otherUnitsVL.map((item) => (
                  <option value={item[0]} key={item[0]}>
                    {item[1]}
                  </option>
                ))}
              </Select>
            )}
          </Box>
          <Button
            variant="action"
            disabled={!(min || max)}
            aria-label="Clear"
            onClick={() => reset()}
          >
            <FiSlash />
          </Button>
        </Flex>
      </Box>
    </FilterBox>
  )
}

export default Numeric
