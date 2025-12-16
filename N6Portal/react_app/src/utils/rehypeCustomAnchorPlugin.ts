import { visit } from 'unist-util-visit';
import type { Root, Element } from 'hast';
import { toString } from 'hast-util-to-string';

const KB_ANCHOR_PREFIX = 'n6kb-';

function toHex2chars(code: number): string {
  return code.toString(16).padStart(2, '0');
}

function phraseToAnchor(phrase: string): string {
  const normalized = phrase.trim().toLowerCase();

  let result = '';

  for (let i = 0; i < normalized.length; i++) {
    const char = normalized[i];
    const code = char.charCodeAt(0);

    // a-z
    if (code >= 97 && code <= 122) {
      result += char;
      continue;
    }

    // 0-9
    if (code >= 48 && code <= 57) {
      result += char;
      continue;
    }

    // space ASCII -> '-'
    if (code === 32) {
      result += '-';
      continue;
    }

    // other ASCII characters (0–127) -> '_' + 2‑characters hex
    if (code < 128) {
      result += `_${toHex2chars(code)}`;
      continue;
    }

    // non-ASCII – skip... (for now?)
  }

  return result;
}

export default function rehypeCustomAnchorPlugin() {
  return (tree: Root) => {
    const seenIds = new Map<string, number>();

    visit(tree, 'element', (node: Element) => {
      if (['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(node.tagName)) {
        if (!node.properties || !node.properties.id) {
          const text = toString(node);
          if (!text.trim()) return;

          const anchor = phraseToAnchor(text);
          if (!anchor) return;

          const baseId = `${KB_ANCHOR_PREFIX}${anchor}`;

          const current = seenIds.get(baseId) ?? 0;
          const next = current + 1;
          seenIds.set(baseId, next);

          const finalId = next === 1 ? baseId : `${baseId}__${next}`;

          node.properties = node.properties || {};
          node.properties.id = finalId;
        }
      }
    });
  };
}
