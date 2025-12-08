import useSWRImmutable from 'swr/immutable'

import { Link } from '../Primitives'
import providers from '../providers.json'

function FacilityList() {
  const [infoUrl] = process.env.REACT_APP_API.split('/api')
  const { data } = useSWRImmutable(infoUrl)

  return (
    <ul>
      {providers
        .filter((source) => data.data_providers.includes(source.url))
        .map((source) => (
          <li key={source.name}>
            <Link href={source.homepage} blank>
              {source.name}
            </Link>
          </li>
        ))}
    </ul>
  )
}

export default FacilityList
