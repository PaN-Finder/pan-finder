import React from 'react'
import { Link as RebassLink } from 'rebass/styled-components'

function Link({ blank, noUnderline, sx, ...props }) {
  return (
    <RebassLink
      target={blank && '_blank'}
      sx={{
        ':hover': noUnderline && { textDecoration: 'none' },
        ...sx,
      }}
      {...props}
    />
  )
}

export default Link
