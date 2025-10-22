import create from 'zustand'

// const preset =
//   localStorage.getItem('isDark') === 'true' ||
//   window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
//     ? true
//     : false;

export const useAppStore = create(() => ({
  isDark: true, // preset,
  // toggleTheme: () => {
  //   const newTheme = !get().isDark;
  //   localStorage.setItem('isDark', newTheme);
  //   set(() => ({ isDark: newTheme }));
  // },
}))

export const useSearchStore = create((set, get) => ({
  count: undefined,
  setCount: (count) => set(() => ({ count })),
  search: '',
  setSearch: (search) => {
    if (search !== get().search) {
      set({ search })
    }
  },
}))
