import { useSyncExternalStore } from 'react'

function createStore(initializer) {
  let state
  const listeners = new Set()

  const getState = () => state

  const setState = (partial) => {
    const nextState = typeof partial === 'function' ? partial(state) : partial

    if (!nextState) {
      return
    }

    state = { ...state, ...nextState }
    listeners.forEach((listener) => listener())
  }

  const subscribe = (listener) => {
    listeners.add(listener)

    return () => {
      listeners.delete(listener)
    }
  }

  state = initializer(setState, getState)

  return function useStore(selector = (snapshot) => snapshot) {
    return useSyncExternalStore(subscribe, () => selector(getState()))
  }
}

// const preset =
//   localStorage.getItem('isDark') === 'true' ||
//   window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
//     ? true
//     : false;

export const useAppStore = createStore(() => ({
  isDark: true, // preset,
  // toggleTheme: () => {
  //   const newTheme = !get().isDark;
  //   localStorage.setItem('isDark', newTheme);
  //   set(() => ({ isDark: newTheme }));
  // },
}))

export const useSearchStore = createStore((set, get) => ({
  count: undefined,
  setCount: (count) => set(() => ({ count })),
  search: '',
  setSearch: (search) => {
    if (search !== get().search) {
      set({ search })
    }
  },
}))
