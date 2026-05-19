import { Textarea } from '@rebass/forms'
import React from 'react'
import { FiSearch, FiRotateCw } from 'react-icons/fi'

import { Box, Button, Flex, Text } from '../../Primitives'

const exampleQueries = [
  'Retrieve datasets where the donor cause of death is cancer.',
  'Look for datasets where the publisher is ESS.',
  'Find datasets with a magnetic field of -100 microtesla.',
  "Look for datasets where the instrument's source current was 10 µA (in either polarity)",
  'Find datasets with an incident wavelength was about 153 picometer.',
  'Find datasets with a source-to-sample distance of 28 meters.',
  'Document where the DOI is 10.15151/ESRF-ES-1317814821.',
  'Find datasets from the Munich Crystallography BAG experiment conducted at the ID23-1 instrument between March 12 and July 27, 2018, where the resolution is less than 2.1 and the number of images is 2.',
  'Look for research proposals involving the D50 T tomograph where the sample formula includes Si, O, K, Al, Na and the publication year is 2018.',
  'Look for research on magnetic diffuse scattering in CuMnO2 where the temperature is between 1.5 K and 300 K and the sample mass is 10,000.',
  'Look for research about Crystal structure where the publication year is 2025.',
]

const feedbackMailbox = ['pan-finder', 'ess.eu']

function SearchForm({
  inputValue,
  handleInputChange,
  handleKeyDown,
  handleSubmit,
  isLoading,
  setInputValue,
  handleClear,
  hasResults = false,
  disabled = false,
}) {
  const feedbackEmail = `${feedbackMailbox[0]}@${feedbackMailbox[1]}`

  const handleFeedbackClick = () => {
    window.location.href = `mailto:${feedbackEmail}`
  }

  return (
    <Box as="form" onSubmit={handleSubmit}>
      <Box sx={{ width: '100%', position: 'relative', mb: 3 }}>
        <Box
          sx={{
            position: 'relative',
            overflow: 'hidden',
            borderRadius: '8px',
            '::before': {
              content: '""',
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: '1px',
              background:
                'linear-gradient(90deg, transparent 0%, #2472b3 20%, #646eb1 50%, #bb4677 80%, transparent 100%)',
              opacity: 0.6,
              zIndex: 1,
            },
          }}
        >
          <Textarea
            value={inputValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Enter search text... (e.g., 'datasets where publisher is ESS')"
            disabled={disabled}
            sx={{
              width: '100%',
              height: '100px',
              fontSize: 'large',
              resize: 'vertical',
              paddingRight: '50px',
              border: '1px solid #646eb1',
              borderRadius: '8px',
              opacity: disabled ? 0.6 : 1,
              cursor: disabled ? 'not-allowed' : 'text',
              position: 'relative',
              zIndex: 0,
            }}
          />
        </Box>
        <Button
          aria-label="Search"
          type="submit"
          disabled={isLoading || disabled}
          variant="buttons.base"
          sx={{
            position: 'absolute',
            top: '8px',
            right: '8px',
            minWidth: 'auto',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            px: '10px',
            py: '10px',
            bg: '#1a202c',
            border: '1px solid #4a5568',
            borderRadius: '6px',
            color: '#e2e8f0',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            ':hover': {
              bg: '#2d3748',
              borderColor: '#646eb1',
              color: '#e2e8f0',
              transform: 'translateY(-1px)',
              boxShadow: '0 2px 8px rgba(100, 110, 177, 0.3)',
            },
            ':active': {
              transform: 'translateY(0)',
            },
            '&:disabled': {
              opacity: 0.6,
              cursor: 'not-allowed',
            },
          }}
        >
          <FiSearch size={14} />
        </Button>
        {handleClear && hasResults && (
          <Button
            aria-label="New Search"
            type="button"
            onClick={handleClear}
            title="Clear search and reset results"
            disabled={disabled}
            variant="buttons.base"
            sx={{
              position: 'absolute',
              bottom: '8px',
              right: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 2,
              px: '4px',
              py: '4px',
              color: '#afb3b9ff',
              fontSize: '12px',
              fontWeight: '500',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              ':hover': {
                color: '#e2e8f0',
                transform: 'translateY(-1px)',
              },
              ':active': {
                transform: 'translateY(0)',
              },
              '&:disabled': {
                opacity: 0.6,
                cursor: 'not-allowed',
              },
            }}
          >
            <FiRotateCw size={13} />
            New Search
          </Button>
        )}
      </Box>

      <Flex
        as="p"
        sx={{
          mt: -1,
          mb: 3,
          alignItems: 'center',
          justifyContent: 'center',
          gap: 2,
          flexWrap: 'wrap',
          textAlign: 'center',
          fontSize: 0,
          color: 'muted',
          opacity: disabled ? 0.6 : 0.8,
        }}
      >
        <Text as="span" sx={{ color: 'inherit' }}>
          We need your feedback. Please share it at
        </Text>
        <Box
          as="button"
          type="button"
          onClick={handleFeedbackClick}
          disabled={disabled}
          sx={{
            appearance: 'none',
            border: '1px solid',
            borderColor: 'rgba(100, 110, 177, 0.35)',
            borderRadius: '999px',
            bg: 'rgba(100, 110, 177, 0.08)',
            color: 'inherit',
            fontSize: 'inherit',
            lineHeight: 1.2,
            px: 3,
            py: 1,
            cursor: disabled ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s ease',
            ':hover': disabled
              ? undefined
              : {
                  bg: 'rgba(100, 110, 177, 0.16)',
                  borderColor: 'rgba(100, 110, 177, 0.6)',
                },
            '&:disabled': {
              opacity: 0.6,
            },
          }}
        >
          {feedbackMailbox[0]}
          <span aria-hidden="true"> [at] </span>
          {feedbackMailbox[1]}
        </Box>
      </Flex>

      {/* Example queries */}
      <Box
        sx={{
          textAlign: 'center',
          transition: 'all 0.4s ease-in-out',
          opacity: isLoading || hasResults ? 0 : 1,
          maxHeight: isLoading || hasResults ? '0px' : '500px',
          overflow: 'hidden',
          transform:
            isLoading || hasResults ? 'translateY(-20px)' : 'translateY(0)',
        }}
      >
        <Text
          as="p"
          sx={{
            mb: 3,
            fontWeight: 'medium',
            fontSize: 1,
            opacity: disabled ? 0.6 : 1,
          }}
        >
          Try these example queries:
        </Text>
        <Flex sx={{ flexWrap: 'wrap', justifyContent: 'center', gap: 2 }}>
          {exampleQueries.map((query) => (
            <Button
              key={query}
              disabled={isLoading || disabled}
              onClick={() => setInputValue(query)}
              variant="outline"
              sx={{
                fontSize: 0,
                padding: '8px 12px',
                borderRadius: '16px',
                border: '1px solid',
                borderColor: '#4a5568',
                bg: 'background',
                color: 'text',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                textAlign: 'left',
                '&:hover': {
                  bg: '#4a5568',
                  transform: 'translateY(-1px)',
                },
                '&:disabled': {
                  opacity: 0.6,
                  cursor: 'not-allowed',
                },
              }}
            >
              {query.length > 60 ? `${query.slice(0, 60)}...` : query}
            </Button>
          ))}
        </Flex>
      </Box>
    </Box>
  )
}

export default SearchForm
