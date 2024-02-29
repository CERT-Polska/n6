import { IAddress, IResponseTableData, IResponse, IResponseParsedAddress } from 'api/services/globalTypes';

const parseAddress = (address?: IAddress[]): IResponseParsedAddress => {
  const initialObject = { ip: '', cc: '', asn: '' };
  if (!address) return initialObject;
  return address.reduce<IResponseParsedAddress>((acc, curr) => {
    acc.ip = `${acc.ip}${curr.ip || ''}\n`;
    acc.cc = `${acc.cc}${curr.cc || ''}\n`;
    acc.asn = `${acc.asn}${curr.asn || ''}\n`;
    return acc;
  }, initialObject);
};

export const parseResponseData = (data: IResponse[]): IResponseTableData[] => {
  return data.map((item: IResponse) => {
    const { address, ...rest } = item;
    const time = rest['time'].toString().replace('T', ' ').replace('Z', ' ');
    const addressData: IResponseParsedAddress = parseAddress(address);
    return { ...rest, time, ...addressData };
  });
};

const parseAddressForCsv = (address?: IAddress[]): IResponseParsedAddress => {
  const initialObject = { ip: '', cc: '', asn: '' };
  if (!address) return initialObject;

  return address.reduce<IResponseParsedAddress>((acc, curr, currIndex, array) => {
    const endOfLine = array.length > 1 && currIndex + 1 < array.length ? ' ' : '';

    acc.ip = `${acc.ip}${curr.ip || ''}${endOfLine}`;
    acc.cc = `${acc.cc}${curr.cc || ''}${endOfLine}`;
    acc.asn = `${acc.asn}${curr.asn || ''}${endOfLine}`;
    return acc;
  }, initialObject);
};

export const parseResponseDataForCsv = (data: IResponse[]): IResponse[] => {
  return data.map((item: IResponse) => {
    const { address, ...rest } = item;
    const addressData: IResponseParsedAddress = parseAddressForCsv(address);
    return { ...rest, ...addressData };
  });
};
