import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import PanFinderPage from './PanFinderPage'

const mockClearDocumentData = jest.fn()
const mockRephraseQuery = jest.fn()
const mockSearch = jest.fn()

jest.mock('@rebass/forms', () => ({
  Textarea: ({ sx, ...props }) => <textarea {...props} />,
}))

jest.mock('../Primitives', () => ({
  Box: ({ as: Component = 'div', sx, variant, children, ...props }) => (
    <Component {...props}>{children}</Component>
  ),
  Button: ({ as: Component = 'button', sx, variant, children, ...props }) => (
    <Component {...props}>{children}</Component>
  ),
  Flex: ({ as: Component = 'div', sx, variant, children, ...props }) => (
    <Component {...props}>{children}</Component>
  ),
  Text: ({ as: Component = 'span', sx, variant, children, ...props }) => (
    <Component {...props}>{children}</Component>
  ),
}))

jest.mock('./components/ErrorDisplay', () => () => null)
jest.mock('./components/FacilitiesSection', () => () => null)
jest.mock('./components/PanFinderFooter', () => () => null)
jest.mock('./components/PageHeader', () => () => null)
jest.mock('./components/QueryDetails', () => () => null)
jest.mock('./components/ResultsDisplay', () => () => null)
jest.mock('./components/StreamingSteps', () => () => null)
jest.mock(
  './components/TurnstileSessionGate',
  () =>
    ({ children }) =>
      children,
)

jest.mock('./contexts/DocumentDataContext', () => ({
  useDocumentData: () => ({
    explanations: {},
    documentDetails: {},
    setExplanation: jest.fn(),
    setDocumentDetails: jest.fn(),
    setDocumentDetailsError: jest.fn(),
    setExplanationError: jest.fn(),
    clearAll: mockClearDocumentData,
  }),
}))

jest.mock('./contexts/SessionContext', () => ({
  useSession: () => ({
    error: null,
  }),
}))

jest.mock('./hooks/usePanFinderApi', () => ({
  usePanFinderApi: () => ({
    data: null,
    error: null,
    isLoading: false,
    isRephrasing: false,
    streamingSteps: [],
    rephraseQuery: mockRephraseQuery,
    search: mockSearch,
    searchWithQueryComponents: jest.fn(),
    fetchDocumentDetails: jest.fn(),
    explainDocument: jest.fn(),
    createSession: jest.fn(),
    reset: jest.fn(),
  }),
}))

describe('PanFinderPage', () => {
  beforeEach(() => {
    mockClearDocumentData.mockReset()
    mockRephraseQuery.mockReset()
    mockSearch.mockReset()
  })

  test('replaces the input with the rewritten query and searches with it', async () => {
    const rewrittenQuery =
      'Retrieve all organ records associated with donor ID LADAF-2021-17.'
    mockRephraseQuery.mockResolvedValue(rewrittenQuery)
    mockSearch.mockResolvedValue(undefined)

    render(<PanFinderPage />)

    fireEvent.change(screen.getByPlaceholderText(/enter search text/i), {
      target: { value: 'Show me all organs from donor LADAF-2021-17' },
    })
    fireEvent.click(screen.getByRole('button', { name: /rephrase query/i }))

    await waitFor(() => {
      expect(mockRephraseQuery).toHaveBeenCalledWith(
        'Show me all organs from donor LADAF-2021-17',
      )
    })
    await waitFor(() => {
      expect(mockSearch).toHaveBeenCalledWith(rewrittenQuery, {
        resetStreamingSteps: false,
      })
    })

    expect(screen.getByPlaceholderText(/enter search text/i)).toHaveValue(
      rewrittenQuery,
    )
    expect(mockClearDocumentData).toHaveBeenCalledTimes(1)
  })
})
