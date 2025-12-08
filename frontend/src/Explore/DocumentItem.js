import { useState } from 'react'
import { FiChevronRight, FiExternalLink, FiChevronUp } from 'react-icons/fi'

import { formatDateVerbose } from '../App/helpers'
import { Card, Box, Flex, Heading, Link, Button, Text } from '../Primitives'
import providers from '../providers.json'
import DetailView from './DetailView'
import ScoringIndicator from './ScoreIndicator'

function DocumentItem(props) {
  const { document } = props
  const {
    pid,
    title,
    score,
    doi,
    summary,
    releaseDate,
    provider: providerURL,
  } = document
  const provider = providers.find((provider) => providerURL === provider.url)

  const doiLink = `http://doi.org/${doi}`
  const [isDetailed, setIsDetailed] = useState(false)

  return (
    <Box
      as="article"
      sx={{
        display: ['block', 'flex'],
        overflow: 'hidden',
      }}
    >
      <Card width={1} key={pid} pb={isDetailed ? 0 : 1}>
        <Box
          sx={{
            cursor: 'pointer',
            ':hover [data-title]': { textDecoration: 'underline' },
          }}
          onClick={(evt) => {
            evt.currentTarget.querySelector('a').click()
          }}
        >
          <Flex
            sx={{
              mb: 2,
              justifyContent: 'space-between',
              flexWrap: 'wrap-reverse',
            }}
          >
            <Flex sx={{ color: 'primary', alignItems: 'center', fontSize: 1 }}>
              <Text as="span" mr={2}>
                {doi}
              </Text>
              <FiExternalLink />
            </Flex>
            <ScoringIndicator score={score} />
          </Flex>
          <Heading
            as={Link}
            href={doiLink}
            data-title
            target="_blank"
            onClick={(evt) => {
              evt.stopPropagation()
            }}
            sx={{
              display: 'block',
              textDecoration: 'none',
              ...(!isDetailed && {
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }),
            }}
          >
            {title}
          </Heading>
          <Box
            sx={
              !isDetailed && {
                display: '-webkit-box',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                '-webkit-line-clamp': '2',
                '-webkit-box-orient': 'vertical',
              }
            }
          >
            {summary}
          </Box>
        </Box>
        {!isDetailed && (
          <Flex
            sx={{
              flexDirection: ['column', 'row'],
              alignItems: ['flex-start', 'center'],
              fontSize: [1, 1, 2],
              mt: 1,
              py: 2,
            }}
          >
            <Button
              variant="base"
              sx={{
                flex: 'none',
                py: 1,
                ':hover': { textDecoration: 'underline' },
              }}
              onClick={() => {
                setIsDetailed(true)
              }}
            >
              <FiChevronRight />
              <Text as="span" ml={2}>
                Details, services ...
              </Text>
            </Button>
            {(releaseDate || provider) && (
              <Text
                as="p"
                sx={{
                  m: 0,
                  my: [2, 0],
                  flex: '1 1 0%',
                  textAlign: 'right',
                  order: [-1, 0],
                }}
              >
                Released
                {provider && (
                  <>
                    {' '}
                    by{' '}
                    <Link
                      href={provider.homepage}
                      blank
                      sx={{ fontWeight: 'bold', letterSpacing: '0.03em' }}
                    >
                      {provider.abbr}
                    </Link>
                  </>
                )}
                {releaseDate && <> on {formatDateVerbose(releaseDate)}</>}
              </Text>
            )}
          </Flex>
        )}
        {isDetailed && <DetailView {...document} />}
        {isDetailed && (
          <Flex>
            <Button
              variant="base"
              onClick={() => setIsDetailed(false)}
              sx={{
                flex: '1 1 0%',
                display: 'flex',
                justifyContent: 'center',
                py: 2,
                mx: -3,
                fontSize: 3,
                ':hover': { bg: 'foreground' },
                ':focus': { outlineOffset: '-2px' },
              }}
            >
              <FiChevronUp />
            </Button>
          </Flex>
        )}
      </Card>
    </Box>
  )
}

export default DocumentItem
