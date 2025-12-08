import { stripEmptyKeys, CHAR } from '../App/helpers'
import { useQuery } from '../router-utils'

const parseList = (str) => str.split(CHAR.join).map((x) => Number.parseFloat(x))

export const makeFilter = (id, stringifiedFilter) => {
  const [val, operator, unit] = stringifiedFilter.split(CHAR.split)

  const value = operator === 'between' ? parseList(val) : val

  return stripEmptyKeys({ id, value, operator, unit })
}

function useFilters() {
  // Update state of every filter based on query params
  const query = useQuery()

  return [...query.entries()].map(([k, v]) => makeFilter(k, v))
}

export default useFilters
