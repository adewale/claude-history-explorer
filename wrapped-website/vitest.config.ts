import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/coverage.test.ts'],
    coverage: {
      provider: 'istanbul',
      include: ['src/**/*.ts'],
      all: true,
      reporter: ['text', 'json'],
    },
  },
});
