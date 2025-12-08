import { useToggle } from '@react-hookz/web'
import { Select } from '@rebass/forms/styled-components'
import { useEffect } from 'react'

import useFilters from '../Api/useFilters'
import { Link, Flex, Box, Text } from '../Primitives'
import { useQueryParam } from '../router-utils'
import { useSearchStore } from './stores'

const COUNT_OPTIONS = ['25', '50', '100', '250']

function ResultsCount() {
  const defaultValue = process.env.REACT_APP_LIMIT || COUNT_OPTIONS[0]

  const count = useSearchStore((state) => state.count)

  const { value, setValue } = useQueryParam('limit')

  const [showSelect, toggleShowSelect] = useToggle()

  const strFilters = JSON.stringify(useFilters())
  const setCount = useSearchStore((state) => state.setCount)

  useEffect(() => {
    strFilters && setCount()
  }, [strFilters, setCount])

  return (
    count === undefined || (
      <Flex alignItems="center">
        <Box px={2} minWidth="fit-content">
          {showSelect ? (
            <Select
              id="limit"
              name="limit"
              value={value || defaultValue}
              onChange={(e) => {
                setValue(e.target.value)
                toggleShowSelect()
                setCount()
              }}
              sx={{
                overflow: 'visible',
                paddingRight: 4,
              }}
            >
              {value !== 'null' && !COUNT_OPTIONS.includes(value) && (
                <option key={value}>{value}</option>
              )}
              {COUNT_OPTIONS.map((option) => (
                <option key={option}>{option}</option>
              ))}
            </Select>
          ) : (
            <Link onClick={() => toggleShowSelect()} as={Text}>
              {count === Number.parseInt(value || defaultValue)
                ? `${count}+`
                : count}
            </Link>
          )}
        </Box>
        <Text as="span">{`document${count === 1 ? '' : 's'}`} found</Text>
      </Flex>
    )
  )
}

export default ResultsCount
