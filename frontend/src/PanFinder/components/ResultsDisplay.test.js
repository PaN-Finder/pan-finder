import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'

import ResultsDisplay from './ResultsDisplay'

jest.mock('../../Primitives', () => ({
  Box: ({ children, ...props }) => <div {...props}>{children}</div>,
}))

jest.mock(
  './ExportCSVButton',
  () =>
    ({ results }) =>
      results.length > 0 ? (
        <div data-testid="export-results-count">{results.length}</div>
      ) : null,
)

jest.mock('./NoResults', () => () => <div>No results found</div>)

jest.mock(
  './ResultsTable',
  () =>
    ({ title, results }) =>
      results.length > 0 ? (
        <div data-testid={`table-${title}`}>
          <span>{title}</span>
          <span>{results.map((result) => result.doi).join(',')}</span>
        </div>
      ) : null,
)

function createProps(overrides = {}) {
  return {
    data: null,
    expandedRows: new Set(),
    documentDetails: {},
    loadingDetails: new Set(),
    handleRowExpand: jest.fn(),
    ...overrides,
  }
}

describe('ResultsDisplay', () => {
  test('splits results into match, relevant, and suggested groups', async () => {
    const handleRowExpand = jest.fn()

    render(
      <ResultsDisplay
        {...createProps({
          handleRowExpand,
          data: {
            id: 'stat-1',
            relevant_results: [
              { doi: '10.match-high', overall_score: 0.99 },
              { doi: '10.match-low', overall_score: 0.95 },
              { doi: '10.relevant', overall_score: 0.94 },
            ],
            weakly_relevant_results: [
              { doi: '10.suggested', overall_score: 0.7 },
            ],
          },
        })}
      />,
    )

    expect(screen.getByTestId('table-Match')).toHaveTextContent(
      '10.match-high,10.match-low',
    )
    expect(screen.getByTestId('table-Relevant Documents')).toHaveTextContent(
      '10.relevant',
    )
    expect(screen.getByTestId('table-Suggested Documents')).toHaveTextContent(
      '10.suggested',
    )
    expect(screen.getByTestId('export-results-count')).toHaveTextContent('4')

    await waitFor(() => {
      expect(handleRowExpand).toHaveBeenCalledWith('10.match-high')
    })
  })

  test('hides the match group when no result reaches the threshold', async () => {
    const handleRowExpand = jest.fn()

    render(
      <ResultsDisplay
        {...createProps({
          handleRowExpand,
          data: {
            id: 'stat-2',
            relevant_results: [
              { doi: '10.relevant-first', overall_score: 0.94 },
              { doi: '10.relevant-second', overall_score: 0.91 },
            ],
            weakly_relevant_results: [],
          },
        })}
      />,
    )

    expect(screen.queryByTestId('table-Match')).not.toBeInTheDocument()
    expect(screen.getByTestId('table-Relevant Documents')).toHaveTextContent(
      '10.relevant-first,10.relevant-second',
    )

    await waitFor(() => {
      expect(handleRowExpand).toHaveBeenCalledWith('10.relevant-first')
    })
  })

  test('shows the empty state when there are no results', () => {
    render(
      <ResultsDisplay
        {...createProps({
          data: {
            id: 'stat-3',
            relevant_results: [],
            weakly_relevant_results: [],
          },
        })}
      />,
    )

    expect(screen.getByText('No results found')).toBeInTheDocument()
    expect(screen.queryByTestId('export-results-count')).not.toBeInTheDocument()
  })
})
