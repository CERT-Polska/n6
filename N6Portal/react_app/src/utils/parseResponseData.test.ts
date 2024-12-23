import { IAddress, IResponse, IResponseParsedAddress, IResponseTableData } from 'api/services/globalTypes';
import { parseAddress, parseResponseData, parseAddressForCsv, parseResponseDataForCsv } from './parseResponseData';

describe('parseAddress', () => {
  it('returns empty Address record when given no input', () => {
    expect(parseAddress()).toStrictEqual({ ip: '', cc: '', asn: '' });
  });

  it('returns the same record when given single Address', () => {
    const address: IAddress[] = [
      {
        ip: '1.1.1.1',
        cc: 'PL',
        asn: 1
      }
    ];
    const expected: IResponseParsedAddress = {
      ip: '1.1.1.1\n',
      cc: 'PL\n',
      asn: '1\n'
    };
    expect(parseAddress(address)).toStrictEqual(expected);
  });

  it('returns parsed Addresss with empty newlines when given incomplete data', () => {
    const address: IAddress[] = [
      {
        ip: '1.1.1.1'
      }
    ];
    const expected: IResponseParsedAddress = {
      ip: '1.1.1.1\n',
      cc: '\n',
      asn: '\n'
    };
    expect(parseAddress(address)).toStrictEqual(expected);
  });

  it('combines multiple addresses into new-line separated entries \
     when given array of Address objects', () => {
    const address: IAddress[] = [
      {
        ip: '1.1.1.1',
        cc: 'PL',
        asn: 1
      },
      {
        ip: '2.2.2.2',
        cc: 'EN',
        asn: 2
      }
    ];
    const expected: IResponseParsedAddress = {
      ip: '1.1.1.1\n2.2.2.2\n',
      cc: 'PL\nEN\n',
      asn: '1\n2\n'
    };
    expect(parseAddress(address)).toStrictEqual(expected);
  });

  it('combines multiple addresses into new-line separated entries \
    when given array of incomplete Address objects', () => {
    const address: IAddress[] = [
      {
        ip: '1.1.1.1',
        cc: 'PL',
        asn: 1
      },
      {
        ip: '2.2.2.2',
        cc: 'EN'
      },
      {
        ip: '3.3.3.3'
      },
      {
        ip: '4.4.4.4',
        asn: 2
      }
    ];
    const expected: IResponseParsedAddress = {
      ip: '1.1.1.1\n2.2.2.2\n3.3.3.3\n4.4.4.4\n',
      cc: 'PL\nEN\n\n\n',
      asn: '1\n\n\n2\n'
    };
    expect(parseAddress(address)).toStrictEqual(expected);
  });
});

describe('parseResponseData', () => {
  it('parses IResponse data array using parseAddress and modifying time string', () => {
    const dataEntry: IResponse = {
      id: '',
      source: '',
      confidence: 'low',
      category: 'amplifier',
      time: '2024-01-01T12:00:00Z',
      address: [
        {
          ip: '1.1.1.1',
          cc: 'PL',
          asn: 1
        }
      ]
    };
    const parsedEntry: IResponseTableData = {
      id: '',
      source: '',
      confidence: 'low',
      category: 'amplifier',
      time: '2024-01-01 12:00:00',
      ip: '1.1.1.1\n',
      cc: 'PL\n',
      asn: '1\n'
    };
    const result = parseResponseData([dataEntry, dataEntry]);
    const expected = [parsedEntry, parsedEntry];
    expect(result).toStrictEqual(expected);
  });
});

describe('parseAddressForCsv', () => {
  it('returns empty Address record when given no input', () => {
    expect(parseAddressForCsv()).toStrictEqual({ ip: '', cc: '', asn: '' });
  });

  it('returns the same record when given single Address', () => {
    const address: IAddress[] = [
      {
        ip: '1.1.1.1',
        cc: 'PL',
        asn: 1
      }
    ];
    const expected: IResponseParsedAddress = {
      ip: '1.1.1.1',
      cc: 'PL',
      asn: '1'
    };
    expect(parseAddressForCsv(address)).toStrictEqual(expected);
  });

  it('returns parsed Addresss with empty strings when given incomplete data', () => {
    const address: IAddress[] = [
      {
        ip: '1.1.1.1'
      }
    ];
    const expected: IResponseParsedAddress = {
      ip: '1.1.1.1',
      cc: '',
      asn: ''
    };
    expect(parseAddressForCsv(address)).toStrictEqual(expected);
  });

  it('combines multiple addresses into space separated entries \
    when given array of Address objects', () => {
    const address: IAddress[] = [
      {
        ip: '1.1.1.1',
        cc: 'PL',
        asn: 1
      },
      {
        ip: '2.2.2.2',
        cc: 'EN',
        asn: 2
      }
    ];
    const expected: IResponseParsedAddress = {
      ip: '1.1.1.1 2.2.2.2',
      cc: 'PL EN',
      asn: '1 2'
    };
    expect(parseAddressForCsv(address)).toStrictEqual(expected);
  });

  it('combines multiple addresses into (multi)space separated entries \
    when given array of incomplete Address objects', () => {
    const address: IAddress[] = [
      {
        ip: '1.1.1.1',
        cc: 'PL',
        asn: 1
      },
      {
        ip: '2.2.2.2',
        cc: 'EN'
      },
      {
        ip: '3.3.3.3'
      },
      {
        ip: '4.4.4.4',
        asn: 2
      }
    ];
    const expected: IResponseParsedAddress = {
      ip: '1.1.1.1 2.2.2.2 3.3.3.3 4.4.4.4',
      cc: 'PL EN  ', // NOTE: multiple whitespaces
      asn: '1   2' // NOTE: multiple whitespaces
    };
    expect(parseAddressForCsv(address)).toStrictEqual(expected);
  });
});

describe('parseResponseDataForCsv', () => {
  it('parses IResponse data array using parseAddressForCsv', () => {
    const dataEntry: IResponse = {
      id: '',
      source: '',
      confidence: 'low',
      category: 'amplifier',
      time: '2024-01-01T12:00:00Z',
      address: [
        {
          ip: '1.1.1.1',
          cc: 'PL',
          asn: 1
        }
      ]
    };
    const parsedEntry: IResponseTableData = {
      id: '',
      source: '',
      confidence: 'low',
      category: 'amplifier',
      time: '2024-01-01T12:00:00Z',
      ip: '1.1.1.1',
      cc: 'PL',
      asn: '1'
    };
    const result = parseResponseDataForCsv([dataEntry, dataEntry]);
    const expected = [parsedEntry, parsedEntry];
    expect(result).toStrictEqual(expected);
  });
});
