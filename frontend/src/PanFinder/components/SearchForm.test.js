import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'

import SearchForm from './SearchForm'

jest.mock('@rebass/forms', () => ({
  Textarea: ({ sx, ...props }) => <textarea {...props} />,
}))

jest.mock('../../Primitives', () => ({
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

function createProps(overrides = {}) {
  return {
    inputValue: 'Show me all organs from donor LADAF-2021-17',
    handleInputChange: jest.fn(),
    handleKeyDown: jest.fn(),
    handleSubmit: jest.fn((event) => event.preventDefault()),
    handleRephrase: jest.fn(),
    isLoading: false,
    isRephrasing: false,
    setInputValue: jest.fn(),
    handleClear: jest.fn(),
    hasResults: false,
    disabled: false,
    ...overrides,
  }
}

describe('SearchForm', () => {
  test('calls handleRephrase when the rephrase button is clicked', () => {
    const props = createProps()

    render(<SearchForm {...props} />)

    fireEvent.click(screen.getByRole('button', { name: /rephrase query/i }))

    expect(props.handleRephrase).toHaveBeenCalledTimes(1)
  })

  test('disables rephrase and search buttons while rephrasing', () => {
    render(<SearchForm {...createProps({ isRephrasing: true })} />)

    expect(
      screen.getByRole('button', { name: /rephrase query/i }),
    ).toBeDisabled()
    expect(screen.getByLabelText('Search')).toBeDisabled()
  })
})
