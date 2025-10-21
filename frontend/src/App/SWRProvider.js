import React from 'react'
import { SWRConfig } from 'swr'

async function fetcher(url) {
  const response = await fetch(url)
  if (response.ok) {
    return response.json()
  }

  throw new Error(response.status)
}

function SWRProvider(props) {
  const { children } = props

  return <SWRConfig value={{ suspense: true, fetcher }}>{children}</SWRConfig>
}

export default SWRProvider
