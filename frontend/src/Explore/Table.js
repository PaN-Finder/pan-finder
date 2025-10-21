import { Link, Flex, Box, Heading } from '../Primitives'
import { dark } from '../colors'

const isLink = (x) => Array.isArray(x)

function Table({ data, title }) {
  return (
    <Box sx={{ pb: 3 }}>
      {title && (
        <Heading
          as="h3"
          sx={{
            fontWeight: '600',
            fontSize: [1, 1],
            mb: [1, 1],
          }}
        >
          {title}
        </Heading>
      )}
      <Box sx={{ maxHeight: 200, overflowY: 'auto', mx: -2, px: 2 }}>
        {data.map((row) => {
          return (
            <Flex
              sx={{
                py: 1,
                justifyContent: 'space-between',
                borderBottom: `1px solid ${dark.foreground}`,
                flexWrap: 'wrap',
                ':last-child': {
                  borderBottom: 0,
                },
              }}
              key={JSON.stringify(row)}
            >
              {row.map((field) => {
                return isLink(field) ? (
                  <Link key={row + field} href={field[1]} blank>
                    {field[0]}
                  </Link>
                ) : (
                  <Box key={row + field}>{field}</Box>
                )
              })}
            </Flex>
          )
        })}
      </Box>
    </Box>
  )
}

export default Table
