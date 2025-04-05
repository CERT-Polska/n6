import { dictionary } from 'dictionary';

// tooltips simply don't render when provided with undefined content,
// but providing these keys allows for type validation of
// `organization_card_tooltip_{category as typeof TCategory}`
const KEYS_WITH_ALLOWED_EMPTY_VALUES = [
  'organization_card_tooltip_dns-query',
  'organization_card_tooltip_flow',
  'organization_card_tooltip_flow-anomaly',
  'organization_card_tooltip_other',
  'organization_card_tooltip_scam',
  'organization_card_tooltip_tor'
];

describe('dictionary', () => {
  it('contains the same set of keys both in English and Polish', () => {
    expect(Object.keys(dictionary.en).sort()).toStrictEqual(Object.keys(dictionary.pl).sort());
  });

  it.each([{ dict: dictionary.en }, { dict: dictionary.pl }])(
    'has no empty or undefined values except for allowed ones',
    ({ dict }) => {
      expect(
        Object.entries(dict).filter(
          ([key, value]) => (!KEYS_WITH_ALLOWED_EMPTY_VALUES.includes(key) && !value) || typeof value !== 'string'
        )
      ).toStrictEqual([]);
    }
  );
});
