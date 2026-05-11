#!/usr/bin/env node
// Sync taxonomy from the GMAT app's authoritative constants module to
// data/taxonomy.json. Run whenever server/utils/constants.js changes.
//
//     node scripts/sync_taxonomy.mjs
//
// Override the source path with GMAT_CONSTANTS=/abs/path/to/constants.js
// for non-default checkouts.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DEFAULT_CONSTANTS = path.resolve(
  __dirname,
  '..',
  '..',
  '..',
  'PycharmProjects',
  'GMATPrepAI',
  'server',
  'utils',
  'constants.js'
);
const constantsPath = process.env.GMAT_CONSTANTS || DEFAULT_CONSTANTS;
const outPath = path.resolve(__dirname, '..', 'data', 'taxonomy.json');

if (!fs.existsSync(constantsPath)) {
  console.error(`constants.js not found at ${constantsPath}`);
  console.error('Set GMAT_CONSTANTS to the absolute path of the GMAT app constants file.');
  process.exit(1);
}

// constants.js is CommonJS; load via createRequire.
const require = createRequire(import.meta.url);
const C = require(pathToFileURL(constantsPath).pathname.replace(/^\//, '/'));

const payload = {
  generated_at: new Date().toISOString(),
  source: constantsPath,
  sections: Object.entries(C.SECTIONS).map(([code, label]) => ({ code, label })),
  content_domains: Object.entries(C.CONTENT_DOMAINS).map(([code, v]) => ({ code, ...v })),
  question_types: Object.entries(C.QUESTION_TYPES).map(([code, v]) => ({ code, ...v })),
  fundamental_skills: Object.entries(C.FUNDAMENTAL_SKILLS).map(([code, v]) => ({ code, ...v })),
  difficulty_levels: Object.entries(C.DIFFICULTY_LABELS).map(([level, label]) => ({
    level: Number(level),
    label,
  })),
  difficulty_buckets: C.DIFFICULTY_BUCKETS,
  convergence_options: C.CONVERGENCE_OPTIONS,
  answer_formats: Object.values(C.ANSWER_FORMATS),
  time_budgets_seconds: C.TIME_BUDGETS_SECONDS,
};

fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, JSON.stringify(payload, null, 2) + '\n');
console.log(`Wrote ${outPath} (${Object.keys(payload).length - 2} sections)`);
