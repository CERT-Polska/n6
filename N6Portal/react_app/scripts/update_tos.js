#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const matter = require('gray-matter');
const crypto = require('crypto');

function getTimestampUTC() {
  const dt = new Date();
  const YYYY = dt.getUTCFullYear().toString();
  const MM = String(dt.getUTCMonth() + 1).padStart(2, '0');
  const DD = String(dt.getUTCDate()).padStart(2, '0');
  const hh = String(dt.getUTCHours()).padStart(2, '0');
  const mm = String(dt.getUTCMinutes()).padStart(2, '0');
  return `${YYYY}${MM}${DD}.${hh}${mm}`;
}

function shortHash(content) {
  return crypto.createHash('sha256').update(content).digest('hex').slice(0, 12);
}

const VERSION_REGEX = /^\d{8}\.\d{4}\.[A-Z]{2}\.[0-9a-fA-F]{12}$/;

function safeArchive(mdPath, lang, version) {
  try {
    archiveDocsNonpub(mdPath, lang, version);
  } catch (e) {
    console.warn(`Archiving step failed for ${mdPath}: ${e.message}`);
  }
}

function writeVersionWithArchive(mdPath, newMd, isDocsSource, lang, version) {
  try {
    fs.writeFileSync(mdPath, newMd, 'utf8');
    console.log(`Updated version in source: ${mdPath} -> ${version}`);
    if (isDocsSource) {
      safeArchive(mdPath, lang, version);
    }
    return true;
  } catch (err) {
    console.warn(`Could not write updated version to ${mdPath}: ${err.message}`);
    console.log(`Computed version (source not writable): ${version}`);
    return false;
  }
}

// CLI args
const args = process.argv.slice(2);
const preferPublicOnly = args.includes('public');

function archiveDocsNonpub(srcPath, lang, version) {
  const docsArchiveRoot = path.resolve(__dirname, '..', '..', '..', 'docs-nonpub', 'portal_gui', 'archived-tos', lang);
  const fileName = `${version}.md`;
  const dest = path.resolve(docsArchiveRoot, fileName);
  try {
    fs.mkdirSync(docsArchiveRoot, { recursive: true });
    fs.copyFileSync(srcPath, dest);
    console.log(`Archived ${srcPath} -> ${dest}`);
    return true;
  } catch (err) {
    console.warn(`Failed to archive into docs-nonpub at ${dest}: ${err.message}`);
    // fallback: local temp archive under react_app/archived-tos
    return fallbackArchive(srcPath, lang, fileName);
  }
}

function fallbackArchive(srcPath, lang, fileName) {
  try {
    const ts = getTimestampUTC();
    const fallbackRoot = path.resolve(__dirname, '..', 'archived-tos', `temp-${ts}`, lang);
    fs.mkdirSync(fallbackRoot, { recursive: true });
    const fallbackDest = path.resolve(fallbackRoot, fileName);
    fs.copyFileSync(srcPath, fallbackDest);
    console.log(`Archived to fallback location: ${fallbackDest}`);
    return true;
  } catch (err2) {
    console.warn(`Failed to archive to fallback location: ${err2.message}`);
    return false;
  }
}

function processLocale(lang) {
  const externalMdPath = path.resolve(__dirname, '..', '..', '..', 'docs-nonpub', 'portal_gui', 'locale', 'tos', lang, 'terms.md');
  const defaultMdPath = path.resolve(__dirname, '..', 'src', 'config', 'locale', 'tos', lang, 'terms.md');
  const mdPath = preferPublicOnly ? defaultMdPath : fs.existsSync(externalMdPath) ? externalMdPath : defaultMdPath;

  if (!fs.existsSync(mdPath)) {
    console.warn(`Skipping missing file: ${mdPath}`);
    return;
  }

  const raw = fs.readFileSync(mdPath, 'utf8');
  const parsed = matter(raw);
  const content = parsed.content.trim();
  const meta = parsed.data || {};

  const timestamp = getTimestampUTC();
  const hash = shortHash(content);
  const existingVersion = meta.version || '';
  let existingHash = '';
  if (existingVersion && VERSION_REGEX.test(existingVersion)) {
    existingHash = existingVersion.split('.').pop();
  } else if (existingVersion) {
    console.warn(`Existing version has unexpected format; ignoring: ${existingVersion}`);
  }
  let version;
  if (existingHash === hash && existingVersion) {
    version = existingVersion;
    console.log(`No content changes, version remains ${version}`);
  } else {
    version = `${timestamp}.${lang.toUpperCase()}.${hash}`;
    meta.version = version;
    const newMd = matter.stringify(content, meta);
    const isDocsSource = mdPath === externalMdPath;
    writeVersionWithArchive(mdPath, newMd, isDocsSource, lang, version);
  }
  console.log(`Using source: ${mdPath}\n`);
}

['en', 'pl'].forEach(processLocale);

console.log('TOS update completed.');
