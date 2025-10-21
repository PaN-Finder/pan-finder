import { Flex, Box, Heading, Text, Link, Image } from '../Primitives'

function Footer() {
  return (
    <Flex
      sx={{
        width: '100%',
        bg: 'middleground',
        p: [1, 2, 2, 3],
        justifyContent: 'space-between',
        flexDirection: 'column',
      }}
    >
      <Box as="footer">
        <Box
          as="section"
          sx={{
            padding: '1.25rem 1.875rem',
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-evenly',
            flexDirection: ['column', 'row', 'row', 'row'],
            alignItems: ['flex-start', 'stretch', 'stretch', 'stretch'],
            maxWidth: ['none', 'none', 'none', '1440px'],
          }}
        >
          <Box as="div" sx={{ padding: '1.25rem', minWidth: '12.5rem' }}>
            <Link href="https://www.panosc.eu/" target="_blank">
              <Image
                src="https://www.panosc.eu/wp-content/uploads/2019/04/logo.svg"
                alt="PaNOSC"
              />
            </Link>
          </Box>
          <Box as="div" sx={{ padding: '1.25rem', minWidth: '12.5rem' }}>
            <Heading sx={{ paddingBottom: '0.625rem' }}>Fundings</Heading>
            <Text as="p" style={{ maxWidth: '300px' }}>
              <Image
                src="https://i0.wp.com/expands.eu/wp-content/uploads/2019/09/eulogo.jpg?resize=100%2C67&amp;ssl=1"
                alt="EU Logo"
                sx={{ float: 'left', marginRight: '10px' }}
              />
              This project receives funding from the{' '}
              <i>
                European Union’s Horizon 2020 research and innovation programme{' '}
              </i>
              under grant agreement No 857641
            </Text>
          </Box>
          <Box as="div" sx={{ padding: '1.25rem', minWidth: '12.5rem' }}>
            <Heading sx={{ paddingBottom: '0.625rem' }}>
              Partner Project
            </Heading>
            <Link
              href="https://expands.eu/"
              sx={{ paddingLeft: 0 }}
              target="_blank"
            >
              <Image
                src="https://i0.wp.com/expands.eu/wp-content/uploads/2019/09/Expands_text_header.png?fit=400%2C55&amp;ssl=1"
                sx={{ background: 'white', height: '40px', padding: '10px' }}
                alt="ExPaNDS"
              />
            </Link>
          </Box>
          <Box as="div" sx={{ padding: '1.25rem', minWidth: '12.5rem' }}>
            <Heading sx={{ paddingBottom: '0.625rem' }}>Get in Touch</Heading>
            <Link href="https://twitter.com/Panosc_eu" target="_blank">
              <Image
                src="https://www.panosc.eu/wp-content/uploads/2019/03/icon-twitter.svg"
                alt="Twitter logo"
                sx={{
                  display: 'inline-block',
                  verticalAlign: 'middle',
                  marginRight: '10px',
                }}
              />
              <Box
                as="span"
                style={{
                  display: 'inline-block',
                  verticalAlign: 'middle',
                  fontSize: '28px',
                }}
              >
                Follow us
              </Box>
            </Link>
            <Text as="p" style={{ paddingTop: '1.25rem' }}>
              Something's not right?{' '}
              <Link href="mailto:feedback@panosc.eu" target="_blank">
                Please, let us know!
              </Link>
            </Text>
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
              &copy; 2019, 2022 PaNOSC photon and neutron open science cloud
            </li>
          </ul>
        </Box>
      </Box>
    </Flex>
  )
}
export default Footer
