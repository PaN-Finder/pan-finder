import { FiDownload } from 'react-icons/fi'
import { Box, Text } from '../../../Primitives'
import CollapsibleJsonNode from './CollapsibleJsonNode'

function RawDataViewer({ rawData, rawDataDisplay, onDownload }) {
  return (
    <Box sx={{ position: 'relative' }}>
      <Box
        sx={{
          mt: 2,
          bg: '#111827',
          p: 2,
          borderRadius: '4px',
          border: '1px solid #4a5568',
          maxHeight: '400px',
          overflowY: 'auto',
        }}
      >
        <Box
          sx={{
            position: 'sticky',
            top: 0,
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center',
            zIndex: 1,
            gap: 2,
          }}
        >
          {rawDataDisplay?.isTruncated && (
            <Box
              sx={{
                p: 2,
                bg: '#2d3748',
                borderRadius: '4px',
                flex: 1,
              }}
            >
              <Text sx={{ color: '#f6ad55', fontSize: '12px' }}>
                ⚠️ Content truncated for performance. Showing first{' '}
                {Math.round(50000 / 1024)}KB of{' '}
                {Math.round(rawDataDisplay.originalLength / 1024)}KB
              </Text>
            </Box>
          )}
          <button
            type="button"
            onClick={onDownload}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#63b3ed',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 8px',
              fontSize: '12px',
            }}
            title="Download full raw data as JSON"
          >
            <FiDownload size={14} />
            Download
          </button>
        </Box>
        {typeof rawData === 'object' && rawData !== null ? (
          <CollapsibleJsonNode data={rawData} level={0} />
        ) : (
          <pre
            style={{
              fontSize: '11px',
              color: '#d1d5db',
              margin: 0,
              fontFamily: 'monospace',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {rawDataDisplay?.content || 'No data available'}
          </pre>
        )}
      </Box>
    </Box>
  )
}

export default RawDataViewer
