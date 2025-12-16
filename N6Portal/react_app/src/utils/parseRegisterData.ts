import { IStepTwoForm } from 'components/pages/signUp/SignUpStepTwo';
import { convertArrayToString } from 'utils/convertFormData';

export const getParsedRegisterData = (data: IStepTwoForm): Record<keyof IStepTwoForm, string> => {
  const { notification_emails, asns, fqdns, ip_networks, notification_language, ...rest } = data;
  return {
    ...rest,
    notification_language: notification_language || '',
    notification_emails: convertArrayToString(notification_emails),
    asns: convertArrayToString(asns),
    fqdns: convertArrayToString(fqdns),
    ip_networks: convertArrayToString(ip_networks)
  };
};
