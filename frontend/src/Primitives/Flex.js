import { forwardRef } from 'react'
import { Flex as RebassFlex } from 'rebass/styled-components'

const Flex = forwardRef((props, ref) => {
  const { column, flexDirection, gap, sx, ...otherProps } = props

  return (
    <RebassFlex
      ref={ref}
      sx={{
        flexDirection: flexDirection || (column && 'column'),
        gap,
        ...sx,
      }}
      {...otherProps}
    />
  )
})

export default Flex
