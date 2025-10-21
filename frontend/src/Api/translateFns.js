import { stripEmptyKeys } from '../App/helpers'
import OPERATORS from '../operators.json'
import MAP from '../targets.json'

const FALLBACK_GROUP_OPERATOR = 'and'

const resolveOperator = (id) => OPERATORS[id] || FALLBACK_GROUP_OPERATOR

const RESERVED_IDS = ['include', 'skip', 'limit', 'order', 'q']

const resolvePath = (id, endpoint) => {
  const known = MAP[id]
  const nested = known?.[endpoint]
  const fallback = known?.fallback

  return id === endpoint
    ? null
    : nested
    ? [...nested, id]
    : fallback
    ? [...fallback, id]
    : known
    ? [id]
    : null
}

export function parse(state, endpoint) {
  const config = state.find(({ group }) => group === undefined) || {}
  const { include: included = [] } = config

  const createGroup = (id) => {
    const {
      value,
      operator = resolveOperator(id),
      target = resolvePath(id, endpoint),
    } = state.find((obj) => obj.id === id) || {}

    return {
      id,
      target,
      operator: value || operator,
      filters: state.filter(({ group }) => group === id),
    }
  }

  const uniqueTargets = state.reduce((acc, scope) => {
    const { group } = scope
    return acc.includes(group) || !group ? acc : [...acc, group]
  }, included)

  const groups = uniqueTargets.map(createGroup)

  const include = groups.filter((obj) => obj.target)
  const where = groups.find((obj) => obj.id === endpoint)

  return [include, where, config]
}

const squash = (list) => list.reduce((acc, scope) => ({ ...acc, ...scope }), {})

const groupByLabel = (list) =>
  list.reduce(
    (acc, scope) => ({
      ...acc,
      [scope.id]: [...(acc[scope.id] || []), scope],
    }),
    {},
  )

const parseShortConfig = (filter) =>
  RESERVED_IDS.includes(filter.id) ? { [filter.id]: filter.value } : filter

export function merge(template, state) {
  const idsOfInterest = state.reduce(
    (acc, scope) => [...acc, scope.id, scope.group],
    [],
  )

  const usefulTemplates = template.filter(({ id }) =>
    idsOfInterest.includes(id),
  )

  const byLabel = groupByLabel(
    [...usefulTemplates, ...state].map(parseShortConfig),
  )

  return Object.values(byLabel).map(squash)
}

const addOperator = (operator, list) =>
  list?.length > 1 ? { [operator]: list } : list?.length > 0 ? list[0] : {}

const buildParameter = (item) => {
  const { field, operator, value, unit } = item
  const arr = [
    { name: field },
    { value: operator ? { [operator]: value } : value },
  ]
  return { and: unit ? [...arr, { unit }] : arr }
}

const buildSimple = (item) => {
  const { field, value: val, forcedValue, operator } = item
  const value = forcedValue || val
  return { [field]: operator ? { [operator]: value } : value }
}

const byTargetLength = (list) => {
  const groups = list.filter((i) => i.target)

  const [deepestTarget = []] = groups
    .map(({ target }) => target)
    .sort((a, b) => a.length - b.length)
    .reverse()

  return deepestTarget.reduce((acc, _, idx, list) => {
    const len = list.length - idx
    const layer = groups.filter(({ target }) => target.length === len)

    return [...acc, layer]
  }, [])
}

const buildGroup = (group, acc) => {
  const { filters, operator, target } = group

  const relation = target[target.length - 1]

  const nestedIn = JSON.stringify([...target].slice(0, -1))

  const isParameters = relation === 'parameters'
  const isParameterException =
    isParameters && operator !== 'or' && filters?.length > 0

  const content =
    filters?.map(isParameters ? buildParameter : buildSimple) || []

  const where = !isParameterException && addOperator(operator, content)

  const include = acc[JSON.stringify(target)]
  const scope = stripEmptyKeys({ include, where })

  const buildRegular = (obj) => [stripEmptyKeys(obj)]
  const buildException = (list) =>
    list.map((obj) => ({ relation, scope: { where: obj } }))

  const parsed = isParameterException
    ? buildException(content)
    : buildRegular({ relation, scope })

  return [nestedIn, parsed]
}

const layerReducer = (acc, layer) => {
  const current = layer.map((g) => JSON.stringify(g.target))

  const missing = Object.keys(acc)
    .filter((k) => !current.includes(k))
    .map((str) => ({ target: JSON.parse(str) }))

  const groups = [...missing, ...layer].map((group) => buildGroup(group, acc))

  return groups.reduce(
    (acc, scope) => ({
      ...acc,
      [scope[0]]: [...(acc[scope[0]] || []), ...scope[1]],
    }),
    {},
  )
}

export const createInclude = (groups) =>
  byTargetLength(groups).reduce(layerReducer, {})['[]']

export const createWhere = (group = {}) => {
  const { operator, filters } = group
  const res = filters?.map(buildSimple)
  return addOperator(operator, res)
}
