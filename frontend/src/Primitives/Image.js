import React from 'react'
import { Image as RebassImage } from 'rebass/styled-components'

function Image({ sx, ...props }) {
  return (
    <RebassImage
      sx={{ display: 'block', objectFit: 'cover', ...sx }}
      {...props}
    />
  )
}

export default Image
