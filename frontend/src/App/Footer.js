import { Flex, Box, Heading, Text, Link, Image } from '../Primitives'

function Footer() {
  return (
    <Flex
      sx={{
        fontSize: '12px',
        width: '100%',
        bg: 'middleground',
        p: [1, 2, 2, 3],
        justifyContent: 'space-between',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      <Box as="footer">
        <Box
          as="section"
          sx={{
            padding: '.25rem 1.875rem',
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            flexDirection: ['column', 'row', 'row', 'row'],
            alignItems: ['flex-start', 'stretch', 'stretch', 'stretch'],
            width: '100%',
            maxWidth: ['none', 'none', 'none', '1440px'],
          }}
        >
          <Box
            as="div"
            sx={{
              padding: '1.25rem',
              minWidth: '12.5rem',
              width: ['100%', '33.3333%', '33.3333%', '33.3333%'],
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-start',
            }}
          >
            <Heading sx={{ paddingBottom: '0.625rem' }}>Funding</Heading>
            <Text
              as="p"
              style={{ width: '100%', maxWidth: '500px', textAlign: 'justify' }}
            >
              The{' '}
              <Link
                href="https://oscars-project.eu/projects/pan-finder-photon-and-neutron-federated-knowledge-finder"
                target="_blank"
              >
                PaN-Finder (Photon and Neutron federated knowledge finder)
              </Link>{' '}
              project is founded by the{' '}
              <Link href="https://oscars-project.eu/" target="_blank">
                OSCARS project
              </Link>
              . The authors acknowledge the{' '}
              <Link href="https://oscars-project.eu/" target="_blank">
                OSCARS project
              </Link>
              , which has received funding from the European Commission's
              Horizon Europe Research and Innovation programme under grant
              agreement No. 101129751.
            </Text>
          </Box>
          <Box
            as="div"
            sx={{
              padding: '1.25rem',
              minWidth: '12.5rem',
              width: ['100%', '33.3333%', '33.3333%', '33.3333%'],
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '1rem',
            }}
          >
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '1rem',
                width: '100%',
              }}
            >
              <Image
                src={`${process.env.PUBLIC_URL}/OSCARS.png`}
                sx={{
                  width: '100%',
                  maxWidth: '220px',
                  height: 'auto',
                  objectFit: 'contain',
                }}
                alt="OSCARS"
              />
              <Image
                src={`${process.env.PUBLIC_URL}/EU.png`}
                sx={{
                  width: '100%',
                  maxWidth: '220px',
                  height: 'auto',
                  objectFit: 'contain',
                }}
                alt="European Union"
              />
            </Box>
          </Box>
          <Box
            as="div"
            sx={{
              padding: '1.25rem',
              minWidth: '12.5rem',
              width: ['100%', '33.3333%', '33.3333%', '33.3333%'],
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
            }}
          >
            <Heading sx={{ paddingBottom: '0.625rem' }}>
              Partner Projects
            </Heading>
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '1rem',
                width: '100%',
              }}
            >
              <Link
                href="https://www.panosc.eu/"
                target="_blank"
                sx={{ display: 'inline-flex', alignItems: 'center' }}
              >
                <Image
                  src={`${process.env.PUBLIC_URL}/panosc-logo.svg`}
                  sx={{
                    width: '100%',
                    maxWidth: '220px',
                    height: 'auto',
                    objectFit: 'contain',
                  }}
                  alt="PaNOSC"
                />
              </Link>
              <Link
                href="https://expands.eu/"
                sx={{
                  paddingLeft: 0,
                  display: 'inline-flex',
                  alignItems: 'center',
                }}
                target="_blank"
              >
                <Image
                  src={`${process.env.PUBLIC_URL}/Expands_text_header.png`}
                  sx={{
                    background: 'white',
                    width: '100%',
                    padding: '0.25rem',
                    maxWidth: '220px',
                    height: 'auto',
                    objectFit: 'contain',
                  }}
                  alt="ExPaNDS"
                />
              </Link>
            </Box>
          </Box>
        </Box>

        <Box
          as="section"
          sx={{
            padding: '0 1.875rem',

            maxWidth: ['none', 'none', 'none', '1440px'],
            borderTop: '1px #777 solid',
          }}
        >
          <ul
            style={{
              listStyle: 'none',
              paddingLeft: 0,
              width: '100%',
              display: 'flex',
              flexWrap: 'wrap',
              margin: 0,
            }}
          >
            <li style={{ margin: '14px 0.625rem 0 0.625rem', flex: 1 }}>
              <Link
                href="https://www.panosc.eu/privacy-policy/"
                target="_blank"
              >
                Privacy Policy
              </Link>
            </li>
            <li
              style={{
                margin: '14px 0.625rem 0 0.625rem',
                color: 'rgb(204, 204, 204)',
              }}
            >
              &copy; 2019, 2026 PaNOSC photon and neutron open science cloud
            </li>
          </ul>
        </Box>
      </Box>
    </Flex>
  )
}
export default Footer
