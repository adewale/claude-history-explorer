/**
 * Backwards Compatibility Tests for Wrapped URL Decoding
 *
 * These tests ensure that previously generated URLs continue to decode correctly
 * as we make changes to the decoder. This prevents breaking changes that would
 * make old URLs unusable.
 *
 * Run with: npx tsx tests/backwards-compat.test.ts
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

import { decodeWrappedStoryV3, type WrappedStoryV3 } from '../src/decoder';

// Get directory path
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Test utilities
let passed = 0;
let failed = 0;
const errors: string[] = [];

function assertEqual<T>(actual: T, expected: T, message: string): boolean {
  if (JSON.stringify(actual) === JSON.stringify(expected)) {
    return true;
  }
  errors.push(`  ${message}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  return false;
}

function assertTrue(condition: boolean, message: string): boolean {
  if (condition) {
    return true;
  }
  errors.push(`  ${message}: expected true`);
  return false;
}

function assertAtLeast(actual: number, min: number, message: string): boolean {
  if (actual >= min) {
    return true;
  }
  errors.push(`  ${message}: expected >= ${min}, got ${actual}`);
  return false;
}

interface GoldenUrlCase {
  id: string;
  description: string;
  source: string;
  encoded: string;
  expected_core: Record<string, any>;
  expected_arrays: Record<string, number>;
  expected_first_project?: Record<string, any>;
  expected_tokens?: Record<string, any>;
}

function runTests() {
  console.log('\n=== Backwards Compatibility Tests (TypeScript) ===\n');
  console.log('Verifying all golden URLs decode correctly\n');

  // Load golden URLs
  const goldenPath = path.join(__dirname, '../../tests/fixtures/golden_urls.json');

  if (!fs.existsSync(goldenPath)) {
    console.error(`Golden URLs file not found: ${goldenPath}`);
    process.exit(1);
  }

  const goldenUrls: GoldenUrlCase[] = JSON.parse(fs.readFileSync(goldenPath, 'utf-8'));
  console.log(`Loaded ${goldenUrls.length} golden URL test cases\n`);

  for (const testCase of goldenUrls) {
    errors.length = 0;  // Clear errors for each test
    console.log(`Test: ${testCase.id}`);
    console.log(`  ${testCase.description}`);

    try {
      // Decode the URL
      const story = decodeWrappedStoryV3(testCase.encoded);

      // Verify version
      assertTrue(story.v === 3, 'story version is 3');

      // Verify core fields
      for (const [key, expectedValue] of Object.entries(testCase.expected_core)) {
        const actualValue = (story as any)[key];
        assertEqual(actualValue, expectedValue, `core.${key}`);
      }

      // Verify array lengths
      const arrays = testCase.expected_arrays;
      if (arrays.hm_length) {
        assertEqual(story.hm.length, arrays.hm_length, 'hm length');
      }
      if (arrays.ma_length) {
        assertEqual(story.ma.length, arrays.ma_length, 'ma length');
      }
      if (arrays.mh_length) {
        assertEqual(story.mh.length, arrays.mh_length, 'mh length');
      }
      if (arrays.ms_length) {
        assertEqual(story.ms.length, arrays.ms_length, 'ms length');
      }
      if (arrays.ar_length) {
        assertEqual(story.ar.length, arrays.ar_length, 'ar length');
      }
      if (arrays.sk_length) {
        assertEqual(story.sk.length, arrays.sk_length, 'sk length');
      }
      if (arrays.tp_min_length) {
        assertAtLeast(story.tp.length, arrays.tp_min_length, 'tp min length');
      }
      if (arrays.pc_min_length) {
        assertAtLeast(story.pc.length, arrays.pc_min_length, 'pc min length');
      }
      if (arrays.te_min_length) {
        assertAtLeast(story.te.length, arrays.te_min_length, 'te min length');
      }
      if (arrays.sf_min_length) {
        assertAtLeast(story.sf.length, arrays.sf_min_length, 'sf min length');
      }

      // Verify first project if expected
      if (testCase.expected_first_project && story.tp.length > 0) {
        const firstProject = story.tp[0];
        for (const [key, expectedValue] of Object.entries(testCase.expected_first_project)) {
          const actualValue = (firstProject as any)[key];
          assertEqual(actualValue, expectedValue, `first_project.${key}`);
        }
      }

      // Verify token stats if expected
      if (testCase.expected_tokens) {
        if (testCase.expected_tokens.total !== undefined) {
          assertEqual(story.tk.total, testCase.expected_tokens.total, 'tk.total');
        }
        if (testCase.expected_tokens.has_models) {
          assertTrue(
            story.tk.models !== undefined && Object.keys(story.tk.models).length > 0,
            'tk.models exists and is not empty'
          );
        }
      }

      if (errors.length === 0) {
        console.log(`  ✓ Passed\n`);
        passed++;
      } else {
        console.log(`  ✗ Failed:`);
        for (const err of errors) {
          console.log(err);
        }
        console.log('');
        failed++;
      }
    } catch (e) {
      console.log(`  ✗ Exception: ${e}`);
      console.log('');
      failed++;
    }
  }

  // Summary
  console.log('=== Summary ===');
  console.log(`Passed: ${passed}`);
  console.log(`Failed: ${failed}`);
  console.log('');

  if (failed > 0) {
    console.log('BACKWARDS COMPATIBILITY BROKEN!');
    console.log('Old URLs would fail to decode correctly.');
    console.log('Review changes to encoder/decoder before deploying.');
    process.exit(1);
  } else {
    console.log('All backwards compatibility tests passed!');
    console.log('Old URLs will continue to work.');
  }
}

runTests();
