import { IStepTwoForm } from 'components/pages/signUp/SignUpStepTwo';
import { convertArrayToString } from 'utils/convertFormData';

export const getParsedRegisterData = (data: IStepTwoForm): Record<keyof IStepTwoForm, string> => {
  const { notification_emails, asns, fqdns, ip_networks, ...rest } = data;
  return {
    ...rest,
    notification_emails: convertArrayToString(notification_emails),
    asns: convertArrayToString(asns),
    fqdns: convertArrayToString(fqdns),
    ip_networks: convertArrayToString(ip_networks)
  };
};
