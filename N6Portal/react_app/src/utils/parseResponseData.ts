import format from 'date-fns/format';
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
    const time = format(new Date(rest['time']), 'yyyy-MM-dd HH:mm:ss');
    const addressData: IResponseParsedAddress = parseAddress(address);
    return { ...rest, time, ...addressData };
  });
};
