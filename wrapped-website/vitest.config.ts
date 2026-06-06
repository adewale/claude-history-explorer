import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/coverage.test.ts', 'tests/security.test.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.ts'],
      all: true,
      reporter: ['text', 'json'],
    },
  },
});
