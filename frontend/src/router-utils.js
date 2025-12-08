import { useCallback, useMemo } from 'react'
import { useHistory, useLocation } from 'react-router-dom'

import { stripEmptyKeys } from './App/helpers'

export const JOIN_CHAR = '~'

export function useQuery() {
  return new URLSearchParams(useLocation().search)
}

export function useQueryParam(name) {
  const history = useHistory()
  const query = useQuery()
  const value = query.get(name)

  const setValue = useCallback(
    (val) => {
      const params = new URLSearchParams(query)

      if (val) {
        params.set(name, val)
      } else {
        params.delete(name)
      }

      history.push({ search: params.toString() })
    },
    [history, name, query],
  )

  const remove = useCallback(() => {
    setValue('')
  }, [setValue])

  return {
    value,
    isActive: !!value,
    setValue,
    remove,
  }
}

export function useSetQueryParams() {
  const history = useHistory()
  return (obj) => {
    const onlyActive = stripEmptyKeys(obj)
    const params = new URLSearchParams(Object.entries(onlyActive))
    history.push({ search: params.toString() })
  }
}

export function useListQueryParam(name) {
  const history = useHistory()
  const query = useQuery()

  const rawValue = query.get(name)
  const values = useMemo(
    () => (rawValue ? rawValue.split(JOIN_CHAR) : []),
    [rawValue],
  )

  const toggleValue = useCallback(
    (val) => {
      const list = new Set(values)
      if (list.has(val)) {
        list.delete(val)
      } else {
        list.add(val)
      }

      const params = new URLSearchParams(query)
      if (list.size > 0) {
        params.set(name, [...list].join(JOIN_CHAR))
      } else {
        params.delete(name)
      }

      history.push({ search: params.toString() })
    },
    [history, name, query, values],
  )

  return {
    values,
    isActive: values.length > 0,
    toggleValue,
  }
}
