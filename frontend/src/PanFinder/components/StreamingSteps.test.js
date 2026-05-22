import React from 'react'
import { render, screen } from '@testing-library/react'

import StreamingSteps from './StreamingSteps'

jest.mock('../../Primitives', () => ({
  Box: ({ as: Component = 'div', sx, children, ...props }) => (
    <Component {...props}>{children}</Component>
  ),
  Flex: ({ as: Component = 'div', sx, children, ...props }) => (
    <Component {...props}>{children}</Component>
  ),
  Text: ({ as: Component = 'span', sx, children, ...props }) => (
    <Component {...props}>{children}</Component>
  ),
}))

describe('StreamingSteps', () => {
  test('renders the rephrasing label before analysis steps', () => {
    render(
      <StreamingSteps
        streamingSteps={[
          { event: 'rephrasing_started', timestamp: 1 },
          { event: 'analysis_started', timestamp: 2 },
        ]}
      />,
    )

    expect(screen.getByText('Rephrasing...')).toBeInTheDocument()
    expect(screen.getByText('Analysis started...')).toBeInTheDocument()
  })
})
