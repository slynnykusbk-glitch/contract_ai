export default {
  test: {
    environment: 'jsdom',
    include: ['draft_panel/__tests__/**/*.{test,spec}.ts?(x)'],
    globals: true,
  },
};
