#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const matter = require('gray-matter');
const crypto = require('crypto');

const ALLOWED_LANG = new Set(["en", "pl"]);

function pickSourcePath(lang) {
  if (!ALLOWED_LANG.has(lang)) {
    throw new Error("Invalid language");
  }
  return path.resolve(__dirname, '..', 'src', 'config', 'locale', 'tos', lang, 'terms.md');
}

function emitLocaleModule(lang) {
  const srcPath = pickSourcePath(lang);
  if (!fs.existsSync(srcPath)) {
    console.warn(`Skipping emit for missing source: ${srcPath}`);
    return;
  }

  const raw = fs.readFileSync(srcPath, 'utf8');
  let parsed;
  try {
    parsed = matter(raw);
  } catch (err) {
    console.warn(`Skipping emit for ${srcPath}: failed to parse front-matter: ${err.message}`);
    return;
  }
  if (!parsed || typeof parsed.content !== 'string') {
    console.warn(`Skipping emit for ${srcPath}: no content found after parsing front-matter`);
    return;
  }
  const content = parsed.content.trim();
  const meta = parsed.data || {};

  const outDir = path.resolve(__dirname, '..', 'src', 'config');
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const outPath = path.resolve(outDir, `terms_${lang}.ts`);
  const safeContent = content.replace(/`/g, '\\`');

  function toJsLiteral(value) {
    if (value === null) return 'null';
    if (Array.isArray(value)) {
      return '[' + value.map((v) => toJsLiteral(v)).join(', ') + ']';
    }
    if (typeof value === 'object') {
      const parts = [];
      for (const [k, v] of Object.entries(value)) {
        const key = /^[A-Za-z_$][A-Za-z0-9_$]*$/.test(k) ? k : `'${String(k).replace(/'/g, "\\'")}'`;
        parts.push(`${key}: ${toJsLiteral(v)}`);
      }
      return `{ ${parts.join(', ')} }`;
    }
    if (typeof value === 'string') {
      return `'${value.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`;
    }
    return String(value);
  }

  function computeShortHash(str) {
    return crypto.createHash('sha256').update(str).digest('hex').slice(0, 12);
  }

  const metaLiteral = toJsLiteral(meta);
  const contentHash = computeShortHash(content);
  const moduleContent =
    `// __hash:${contentHash}\n` +
    `const content = \`${safeContent}\`;\n` +
    `const meta = ${metaLiteral};\n` +
    `export default { content, meta };\n`;

  try {
    if (fs.existsSync(outPath)) {
      const existing = fs.readFileSync(outPath, 'utf8');
      const headerMatch = existing.match(/^\/\/\s*__hash:([0-9a-fA-F]+)\s*$/m);
      const existingHash = headerMatch ? headerMatch[1] : computeShortHash(existing);
      if (existingHash === contentHash) {
        console.log(`No changes for ${outPath}; skipping write.`);
      } else {
        fs.writeFileSync(outPath, moduleContent, 'utf8');
        console.log(`Emitted ${outPath} from ${srcPath}`);
      }
    } else {
      fs.writeFileSync(outPath, moduleContent, 'utf8');
      console.log(`Emitted ${outPath} from ${srcPath}`);
    }
  } catch (err) {
    console.error(`Failed to write ${outPath}: ${err.message}`);
  }
}

['en', 'pl'].forEach(emitLocaleModule);

console.log('Emit TOS modules completed.');


