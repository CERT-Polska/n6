import type { Root, Element } from 'hast';
import rehypeCustomAnchorPlugin from './rehypeCustomAnchorPlugin';

jest.mock('unist-util-visit', () => ({
  visit: (tree: Root, type: string, visitor: (node: Element) => void) => {
    const walk = (node: any) => {
      if (node.type === type) visitor(node);
      if (node.children) node.children.forEach(walk);
    };
    walk(tree);
  }
}));

jest.mock('hast-util-to-string', () => ({
  toString: (node: Element): string => {
    const extract = (n: any): string => {
      if (n.type === 'text') return n.value || '';
      if (n.children) return n.children.map(extract).join('');
      return '';
    };
    return extract(node);
  }
}));

const KB_ANCHOR_PREFIX = 'n6kb-';

const makeHeading = (tagName: string, text: string, existingId?: string): Element => ({
  type: 'element',
  tagName,
  properties: existingId ? { id: existingId } : {},
  children: [{ type: 'text', value: text }]
});

const makeTree = (...children: Element[]): Root => ({
  type: 'root',
  children
});

describe('rehypeCustomAnchorPlugin', () => {
  const transform = rehypeCustomAnchorPlugin();

  it('assigns id to heading elements (h1-h6) based on their text content', () => {
    const headings = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] as const;

    headings.forEach((tag) => {
      const heading = makeHeading(tag, 'Hello World');
      const tree = makeTree(heading);
      transform(tree);
      expect(heading.properties!.id).toBe(`${KB_ANCHOR_PREFIX}hello-world`);
    });
  });

  it('does not assign id to non-heading elements', () => {
    const paragraph: Element = {
      type: 'element',
      tagName: 'p',
      properties: {},
      children: [{ type: 'text', value: 'Some text' }]
    };
    const tree = makeTree(paragraph);
    transform(tree);
    expect(paragraph.properties!.id).toBeUndefined();
  });

  it('does not overwrite existing id on heading', () => {
    const heading = makeHeading('h2', 'Some Title', 'my-custom-id');
    const tree = makeTree(heading);
    transform(tree);
    expect(heading.properties!.id).toBe('my-custom-id');
  });

  it('converts lowercase letters and digits as-is', () => {
    const heading = makeHeading('h2', 'abc123');
    const tree = makeTree(heading);
    transform(tree);
    expect(heading.properties!.id).toBe(`${KB_ANCHOR_PREFIX}abc123`);
  });

  it('converts uppercase letters to lowercase', () => {
    const heading = makeHeading('h2', 'Hello');
    const tree = makeTree(heading);
    transform(tree);
    expect(heading.properties!.id).toBe(`${KB_ANCHOR_PREFIX}hello`);
  });

  it('converts spaces to hyphens', () => {
    const heading = makeHeading('h2', 'hello world test');
    const tree = makeTree(heading);
    transform(tree);
    expect(heading.properties!.id).toBe(`${KB_ANCHOR_PREFIX}hello-world-test`);
  });

  it('converts other ASCII characters to _XX hex format', () => {
    const heading = makeHeading('h2', 'hello!');
    const tree = makeTree(heading);
    transform(tree);
    expect(heading.properties!.id).toBe(`${KB_ANCHOR_PREFIX}hello_21`);
  });

  it('skips non-ASCII characters', () => {
    const heading = makeHeading('h2', 'héllo wörld');
    const tree = makeTree(heading);
    transform(tree);
    expect(heading.properties!.id).toBe(`${KB_ANCHOR_PREFIX}hllo-wrld`);
  });

  it('trims whitespace before processing', () => {
    const heading = makeHeading('h2', '  Trimmed Title  ');
    const tree = makeTree(heading);
    transform(tree);
    expect(heading.properties!.id).toBe(`${KB_ANCHOR_PREFIX}trimmed-title`);
  });

  it('skips headings with empty or whitespace-only text', () => {
    const heading = makeHeading('h2', '   ');
    const tree = makeTree(heading);
    transform(tree);
    expect(heading.properties!.id).toBeUndefined();
  });

  it('appends suffix for duplicate heading anchors', () => {
    const h1 = makeHeading('h2', 'duplicate');
    const h2 = makeHeading('h3', 'duplicate');
    const h3 = makeHeading('h4', 'duplicate');
    const tree = makeTree(h1, h2, h3);
    transform(tree);

    expect(h1.properties!.id).toBe(`${KB_ANCHOR_PREFIX}duplicate`);
    expect(h2.properties!.id).toBe(`${KB_ANCHOR_PREFIX}duplicate__2`);
    expect(h3.properties!.id).toBe(`${KB_ANCHOR_PREFIX}duplicate__3`);
  });

  it('handles mixed ASCII special characters correctly', () => {
    const heading = makeHeading('h2', 'a@b');
    const tree = makeTree(heading);
    transform(tree);
    expect(heading.properties!.id).toBe(`${KB_ANCHOR_PREFIX}a_40b`);
  });

  it('produces empty anchor from text with only non-ASCII characters and skips it', () => {
    const heading = makeHeading('h2', 'ąęśćź');
    const tree = makeTree(heading);
    transform(tree);
    expect(heading.properties!.id).toBeUndefined();
  });
});
