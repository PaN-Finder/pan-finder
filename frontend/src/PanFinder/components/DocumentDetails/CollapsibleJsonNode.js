import { useState } from 'react'
import { FiChevronRight, FiChevronDown } from 'react-icons/fi'
import { Box, Text } from '../../../Primitives'

function CollapsibleJsonNode({ data, name, level = 0 }) {
  const [isExpanded, setIsExpanded] = useState(level < 2)

  const isObject =
    typeof data === 'object' && data !== null && !Array.isArray(data)
  const isArray = Array.isArray(data)
  const isCollapsible = isObject || isArray

  const getPreview = () => {
    if (isArray) return `Array(${data.length})`
    if (isObject) return `Object(${Object.keys(data).length})`
    return null
  }

  const indent = level * 20

  if (!isCollapsible) {
    return (
      <Box sx={{ pl: `${indent}px`, py: '2px' }}>
        <Text
          as="span"
          sx={{
            color: '#63b3ed',
            fontSize: '11px',
            fontFamily: 'monospace',
          }}
        >
          {name && (
            <>
              <Text as="span" sx={{ color: '#9f7aea' }}>
                "{name}"
              </Text>
              :{' '}
            </>
          )}
          <Text
            as="span"
            sx={{
              color:
                typeof data === 'string'
                  ? '#48bb78'
                  : typeof data === 'number'
                  ? '#f6ad55'
                  : typeof data === 'boolean'
                  ? '#ed64a6'
                  : '#e2e8f0',
            }}
          >
            {typeof data === 'string' ? `"${data}"` : String(data)}
          </Text>
        </Text>
      </Box>
    )
  }

  return (
    <Box>
      <Box
        sx={{
          pl: `${indent}px`,
          py: '2px',
          cursor: 'pointer',
          '&:hover': {
            bg: 'rgba(99, 179, 237, 0.1)',
          },
        }}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <Text
          as="span"
          sx={{
            color: '#a0aec0',
            fontSize: '11px',
            fontFamily: 'monospace',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {isExpanded ? (
            <FiChevronDown size={12} />
          ) : (
            <FiChevronRight size={12} />
          )}
          {name && (
            <>
              <Text as="span" sx={{ color: '#9f7aea' }}>
                "{name}"
              </Text>
              :{' '}
            </>
          )}
          <Text as="span" sx={{ color: '#e2e8f0' }}>
            {isArray ? '[' : '{'}
          </Text>
          {!isExpanded && (
            <Text as="span" sx={{ color: '#718096', fontStyle: 'italic' }}>
              {getPreview()}
            </Text>
          )}
          {!isExpanded && (
            <Text as="span" sx={{ color: '#e2e8f0' }}>
              {isArray ? ']' : '}'}
            </Text>
          )}
        </Text>
      </Box>
      {isExpanded && (
        <>
          {isArray
            ? data.map((item, index) => (
                <CollapsibleJsonNode
                  key={index}
                  data={item}
                  name={String(index)}
                  level={level + 1}
                />
              ))
            : Object.entries(data).map(([key, value]) => (
                <CollapsibleJsonNode
                  key={key}
                  data={value}
                  name={key}
                  level={level + 1}
                />
              ))}
          <Box sx={{ pl: `${indent}px`, py: '2px' }}>
            <Text
              as="span"
              sx={{
                color: '#e2e8f0',
                fontSize: '11px',
                fontFamily: 'monospace',
              }}
            >
              {isArray ? ']' : '}'}
            </Text>
          </Box>
        </>
      )}
    </Box>
  )
}

export default CollapsibleJsonNode
