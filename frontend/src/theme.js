import { useAppStore } from './App/stores'
import { breakpoints } from './breakpoints'
import { light, dark } from './colors'

export function useTheme() {
  const isDark = useAppStore((state) => state.isDark)

  return {
    colors: isDark ? dark : light,
    breakpoints,
    fonts: {
      text: 'Open Sans, system-ui, sans-serif',
      heading: 'inherit',
    },
    fontSizes: [12, 14, 16, 20, 24, 32, 48, 64, 96],
    fontWeights: {
      light: 300,
      semibold: 600,
      heading: 'normal',
    },
    lineHeights: {
      text: 1.5,
      heading: 1.25,
    },
    space: [0, 4, 8, 16, 32, 64, 128, 256, 512],
    sizes: {
      navHeight: 60,
      logoHeight: 25,
    },
    shadows: {
      rangeHandle: `0 0 0 3px ${isDark ? 'white' : 'black'}`,
    },
    text: {
      heading: {
        color: 'textVivid',
        fontSize: [1, 2, 2, 3],
        lineHeight: 1.25,
        mb: [1, 2],
      },
      display: {
        fontSize: [3, 4, 4, 5],
        fontWeight: 'light',
        mb: 3,
      },
      subHeading: {
        fontSize: [0, 1, 1, 2],
        fontWeight: 'bold',
        mb: 2,
      },
      filter: {
        fontSize: 1,
        mb: 2,
        '&[data-active]': { color: 'textVivid', fontWeight: 'semibold' },
      },
      keyword: {
        bg: 'foreground',
        borderRadius: 0,
        color: 'textVivid',
        fontSize: 0,
        lineHeight: 1.75,
        px: 2,
      },
    },
    variants: {
      card: { p: 3, bg: 'middleground' },
      link: {
        color: 'primary',
        textDecoration: 'none',
        ':hover, :focus-visible, .active': { color: 'text' },
        ':hover': { textDecoration: 'underline' },
      },
    },
    buttons: {
      base: {
        display: 'flex',
        alignItems: 'center',
        textAlign: 'left',
        px: 0,
        py: 0,
        bg: 'transparent',
        border: 'none',
        borderRadius: 0,
        color: 'inherit',
        fontSize: 'inherit',
        cursor: 'pointer',
        outlineOffset: 2,
        ':disabled': { pointerEvents: 'none', opacity: 0.2 },
        ':focus-visible': {
          outlineColor: 'currentColor',
          outlineStyle: 'auto',
        },
      },
      primary: {
        variant: 'buttons.base',
        px: [2, 2, 3],
        py: [1, 1, 2],
        bg: 'foreground',
        color: 'textVivid',
        fontSize: [1, 1, 2],
        fontWeight: 'bold',
        ':hover': { bg: 'bgInverted', color: 'textInverted' },
      },
      secondary: {
        variant: 'buttons.primary',
        fontSize: [0, 0, 1],
        fontWeight: 600,
        py: 1,
      },
      action: {
        variant: 'buttons.base',
        flex: 'none',
        p: 2,
        ml: 2,
        border: '1px solid transparent',
        fontSize: 2,
        ':hover': {
          bg: 'background',
          color: 'textVivid',
          boxShadow: `0 0 2px ${isDark ? 'black' : 'white'}`,
        },
      },
    },
    forms: {
      input: {
        bg: 'highlight',
        fontSize: 0,
        borderRadius: 0,
        borderColor: 'secondary',
      },
      select: {
        width: '100%',
        bg: 'highlight',
        borderRadius: 0,
        fontSize: 0,
        borderColor: 'secondary',
        textOverflow: 'ellipsis',
        overflow: 'hidden',
        option: {
          color: 'black',
        },
      },
      switch: {
        p: '2px',
        bg: 'bgInverted',
        border: 'none',
        cursor: 'pointer',
        '&[aria-checked=true]': { bg: 'ternary' },
        ':focus': { boxShadow: 'none' },
        thumb: {
          border: 'none',
          width: 20,
          height: 20,
          mt: '0',
          ml: '0',
        },
      },
    },
  }
}
