import React from 'react'
import providers from '../../providers.json'
import { Box, Link, Heading } from '../../Primitives'

/**
 * FacilitiesSection - Displays a heading and a vertical, centered list of facility providers.
 * Accepts an optional `only` prop to restrict which facilities are shown by their abbreviation.
 */
function FacilitiesSection({ only = [] }) {
  return (
    <Box
      sx={{
        mt: 5,
        mb: 2,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
        fontSize: '0.875rem',
        '& ul': {
          listStyle: 'none',
          padding: 0,
          margin: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 1,
        },
        '& li': {
          textAlign: 'center',
        },
      }}
    >
      <Heading
        sx={{
          mb: 2,
          textAlign: 'center',
          fontSize: '1.25rem',
        }}
      >
        Open data from the following data sources
      </Heading>
      <ul>
        {providers
          .filter((source) => !only || only.includes(source.abbr))
          .map((source) => (
            <li key={source.name}>
              <Link href={source.homepage} blank>
                {source.name}
              </Link>
            </li>
          ))}
      </ul>
    </Box>
  )
}

export default FacilitiesSection
