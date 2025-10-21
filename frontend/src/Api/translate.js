import { stripEmptyKeys } from '../App/helpers'
import template from '../filters.json'
import { merge, parse, createInclude, createWhere } from './translateFns'

const translate = (state, endpoint = 'documents') => {
  const filters = merge(template, state)

  const [toInclude, toWhere, toRoot] = parse(filters, endpoint)

  const include = createInclude(toInclude)
  const where = createWhere(toWhere)
  const {
    skip,
    limit = process.env.REACT_APP_LIMIT
      ? Number.parseInt(process.env.REACT_APP_LIMIT)
      : 50,
    fields,
    order,
    q: query,
  } = toRoot

  return stripEmptyKeys({
    include,
    where,
    order,
    query,
    skip,
    limit,
    fields,
  })
}

export default translate
