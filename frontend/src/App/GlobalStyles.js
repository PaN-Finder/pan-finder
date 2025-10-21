import css from '@styled-system/css'
import normalize from 'normalize.css'
import { createGlobalStyle } from 'styled-components'

const GlobalStyles = createGlobalStyle`
  ${css({
    normalize,
    '*, *::before, *::after': {
      boxSizing: 'border-box',
    },
    body: {
      bg: 'background',
      color: 'text',
      fontFamily: 'text',
      fontSize: [1, 1, 2],
      lineHeight: 'text',
    },
    ul: {
      listStyleType: 'square',
      color: 'ternary',
    },
  })}

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes fadeInUp {
    0% {
      opacity: 0;
      transform: translateY(10px);
    }
    100% {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes fadeIn {
    0% {
      opacity: 0;
    }
    100% {
      opacity: 1;
    }
  }
`

export default GlobalStyles
