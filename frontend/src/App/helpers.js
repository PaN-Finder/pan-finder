import { format, isValid } from 'date-fns'

export function formatDate(date) {
  const dateObj = new Date(date)
  return isValid(dateObj) ? format(dateObj, 'd. MMMM yyyy') : 'not available'
}

export function formatDateVerbose(date) {
  const dateObj = new Date(date)
  return isValid(dateObj) ? format(dateObj, 'MMMM do yyyy') : ''
}

export function capitalizeAndSpace(str) {
  return `${str[0].toUpperCase()}${str.slice(1).replaceAll('_', ' ')}`
}

const isEmpty = (obj) => JSON.stringify(obj) === '{}'
export const stripEmptyKeys = (obj) =>
  Object.fromEntries(
    Object.entries(obj).filter(
      ([, v]) => ![undefined, ''].includes(v) && !isEmpty(v),
    ),
  )

export const CHAR = {
  join: '~',
  split: "'",
}
