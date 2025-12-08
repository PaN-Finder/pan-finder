import { useDebouncedCallback } from '@react-hookz/web'
import { Input } from '@rebass/forms/styled-components'
import useSWR from 'swr'

import { useQueryParam } from '../router-utils'

function AsynAutocomplete({ obj, isStateful, statefulParam }) {
  const { display, optionsUrl: url, id } = obj
  const name = display.toLowerCase()

  const queryParam = useQueryParam(id)
  const param = isStateful ? statefulParam : queryParam

  const { data: options } = useSWR(url)

  const sortedOptions = [...options].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true }),
  )
  const validNames = sortedOptions.map((opt) => opt.name)

  const handleChange = useDebouncedCallback(
    (evt) => {
      const newVal = evt.target.value
      if (validNames.includes(newVal) || newVal === '') {
        param.setValue(newVal)
      }
    },
    [param],
    1000,
  )

  return (
    <>
      <Input
        aria-label={`${display} list`}
        onChange={handleChange}
        list={`${name}-list`}
        placeholder={`Select a ${name}...`}
        defaultValue={param.value}
        sx={{ flex: '1 1 0%', fontSize: 0 }}
      />
      <datalist id={`${name}-list`}>
        {sortedOptions.map((opt) => (
          <option key={opt.pid}>{opt.name}</option>
        ))}
      </datalist>
    </>
  )
}

export default AsynAutocomplete
