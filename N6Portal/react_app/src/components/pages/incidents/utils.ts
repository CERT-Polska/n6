import { Validate } from 'react-hook-form';
import { SelectOption } from 'components/shared/customSelect/CustomSelect';
import { IRequestParams, TCategory, TProto, TRestriction } from 'api/services/globalTypes';
import {
  validateAsnNumberRequired,
  validatePortNumberRequired,
  validateIpRequired,
  validateIpNetworkRequired,
  validateTargetRequired,
  validateUrlRequired,
  validateUrlPartRequired,
  validateIncidentNameRequired,
  validateFqdnRequired,
  validateFqdnSubRequired,
  validateMd5Required,
  validateSha1Required,
  validateSourceRequired,
  validateCountryCodeRequired,
  validateTimeRequired,
  validateIdRequired,
  validateClientRequired
} from 'components/forms/validation/validationSchema';
import { isRequired } from 'components/forms/validation/validators';

export interface IIncidentsForm
  extends Pick<
    IRequestParams,
    'asn' | 'cc' | 'dport' | 'fqdn' | 'ip' | 'md5' | 'name' | 'sha1' | 'source' | 'sport' | 'target' | 'url'
  > {
  startDate: string;
  startTime: string;
  endDate?: string;
  endTime?: string;
  fqdnSub?: string;
  ipNet?: string;
  urlSub?: string;
  id?: string;
  category?: SelectOption<TCategory>[];
  proto?: SelectOption<TProto>[];
  restriction?: SelectOption<TRestriction>[];
  client?: string;
  nameSub?: string;
}

const categoryList = [
  { value: 'amplifier', label: 'Amplifier' },
  { value: 'backdoor', label: 'Backdoor' },
  { value: 'bots', label: 'Bots' },
  { value: 'cnc', label: 'CNC' },
  { value: 'deface', label: 'Deface' },
  { value: 'dns-query', label: 'DNS query' },
  { value: 'dos-attacker', label: 'DoS attacker' },
  { value: 'dos-victim', label: 'DoS victim' },
  { value: 'flow', label: 'Flow' },
  { value: 'flow-anomaly', label: 'Flow anomaly' },
  { value: 'fraud', label: 'Fraud' },
  { value: 'leak', label: 'Leak' },
  { value: 'malurl', label: 'MalURL' },
  { value: 'malware-action', label: 'Malware action' },
  { value: 'phish', label: 'Phish' },
  { value: 'proxy', label: 'Proxy' },
  { value: 'sandbox-url', label: 'Sandbox URL' },
  { value: 'scam', label: 'Scam' },
  { value: 'scanning', label: 'Scanning' },
  { value: 'server-exploit', label: 'Server exploit' },
  { value: 'spam', label: 'Spam' },
  { value: 'spam-url', label: 'Spam URL' },
  { value: 'tor', label: 'Tor' },
  { value: 'webinject', label: 'Web injection' },
  { value: 'vulnerable', label: 'Vulnerable' },
  { value: 'other', label: 'Other' }
];

const protoList = [
  { value: 'tcp', label: 'TCP' },
  { value: 'udp', label: 'UDP' },
  { value: 'icmp', label: 'ICMP' }
];

const restrictionList = [
  { value: 'public', label: 'Public' },
  { value: 'need-to-know', label: 'Need to know' },
  { value: 'internal', label: 'Internal' }
];

export type TFilterName = keyof IIncidentsForm;

export type TFilter =
  | {
      type: 'input';
      name: TFilterName;
      label: string;
      validate?: Record<string, Validate<string>>;
    }
  | {
      type: 'select';
      name: TFilterName;
      label: string;
      validate?: Record<string, Validate<SelectOption<string | boolean | number> | null>>;
      options: SelectOption<string>[];
    }
  | {
      type: 'date';
      name: TFilterName;
      label: string;
      nameTime: TFilterName;
      labelTime: string;
      validateTimeRequired?: Record<string, Validate<string>>;
    };

type TStoreValue = {
  value?: string | SelectOption<TCategory>[] | SelectOption<TProto>[] | SelectOption<TRestriction>[];
};
type TStoreFilter = ({ isDate: true } | TFilter) & TStoreValue;

export type TStoredFilter = Record<keyof IIncidentsForm, TStoreFilter>;

export const allFilters: TFilter[] = [
  { name: 'asn', label: 'incidents_form_asn', type: 'input', validate: validateAsnNumberRequired },
  {
    name: 'category',
    label: 'incidents_form_category',
    type: 'select',
    options: categoryList,
    validate: { isRequired }
  },
  { name: 'cc', label: 'incidents_form_cc', type: 'input', validate: validateCountryCodeRequired },
  { name: 'client', label: 'incidents_form_client', type: 'input', validate: validateClientRequired },
  { name: 'dport', label: 'incidents_form_dport', type: 'input', validate: validatePortNumberRequired },
  { name: 'fqdn', label: 'incidents_form_fqdn', type: 'input', validate: validateFqdnRequired },
  { name: 'fqdnSub', label: 'incidents_form_fqdn_sub', type: 'input', validate: validateFqdnSubRequired },
  {
    name: 'endDate',
    label: 'incidents_form_end_date',
    type: 'date',
    nameTime: 'endTime',
    labelTime: 'incidents_form_end_time',
    validateTimeRequired: validateTimeRequired
  },
  { name: 'id', label: 'incidents_form_id', type: 'input', validate: validateIdRequired },
  { name: 'ip', label: 'incidents_form_ip', type: 'input', validate: validateIpRequired },
  { name: 'ipNet', label: 'incidents_form_ip_net', type: 'input', validate: validateIpNetworkRequired },
  { name: 'md5', label: 'incidents_form_md5', type: 'input', validate: validateMd5Required },
  { name: 'name', label: 'incidents_form_name', type: 'input', validate: validateIncidentNameRequired },
  { name: 'nameSub', label: 'incidents_form_name_sub', type: 'input', validate: validateIncidentNameRequired },
  {
    name: 'proto',
    label: 'incidents_form_proto',
    type: 'select',
    options: protoList,
    validate: { isRequired }
  },
  {
    name: 'restriction',
    label: 'incidents_form_restriction',
    type: 'select',
    options: restrictionList,
    validate: { isRequired }
  },
  { name: 'sha1', label: 'incidents_form_sha1', type: 'input', validate: validateSha1Required },
  { name: 'source', label: 'incidents_form_source', type: 'input', validate: validateSourceRequired },
  { name: 'sport', label: 'incidents_form_sport', type: 'input', validate: validatePortNumberRequired },
  {
    name: 'target',
    label: 'incidents_form_target',
    type: 'input',
    validate: validateTargetRequired
  },
  { name: 'url', label: 'incidents_form_url', type: 'input', validate: validateUrlRequired },
  { name: 'urlSub', label: 'incidents_form_url_sub', type: 'input', validate: validateUrlPartRequired }
];

export const convertDateAndTime = (date: string, time: string) => {
  const [days, month, year] = date.split('-').map((comp) => parseInt(comp));
  const [hours, minutes] = time.split(':').map((comp) => parseInt(comp));
  const convertedDate = new Date(Date.UTC(year, month - 1, days, hours, minutes));
  return convertedDate;
};

export const convertObjectArrToString = (options: SelectOption<TCategory | TProto | TRestriction>[]): string =>
  options.map((opt) => opt.value).join(',');

export const optLimit = 1000;

export const parseIncidentsFormData = (data: IIncidentsForm): IRequestParams => {
  const {
    category,
    proto,
    fqdnSub,
    ipNet,
    urlSub,
    nameSub,
    startDate,
    startTime,
    endDate,
    endTime,
    restriction,
    ...rest
  } = data;

  const newData = {
    ...rest,
    'time.min': convertDateAndTime(startDate, startTime),
    'opt.limit': optLimit,
    ...(endDate && endTime ? { 'time.max': convertDateAndTime(endDate, endTime) } : {}),
    ...(category ? { category: convertObjectArrToString(category) } : {}),
    ...(proto ? { proto: convertObjectArrToString(proto) } : {}),
    ...(restriction ? { restriction: convertObjectArrToString(restriction) } : {}),
    ...(fqdnSub ? { 'fqdn.sub': fqdnSub } : {}),
    ...(ipNet ? { 'ip.net': ipNet } : {}),
    ...(urlSub ? { 'url.sub': urlSub } : {}),
    ...(nameSub ? { 'name.sub': nameSub } : {})
  };

  return newData;
};
