import localeEN from '../locales/EN/edit_config_form_fields.json';

import {
  email,
  maxLength,
  maxValue,
  integer,
} from 'vuelidate/lib/validators';

import {
  cidr,
  fqdn,
  notificationTime,
} from '../helpers/validators';

let criteria = {
  org_id: {
    id: 'org_id',
    type: 'text',
  },
  actual_name: {
    id: 'actual_name',
    type: 'text',
  },
  notification_enabled: {
    id: 'notification_enabled',
    type: 'checkbox',
  },
  notification_language: {
    id: 'notification_language',
    type: 'radio',
    possible_vals: ['EN', 'PL'],
  },
  notification_emails: {
    id: 'notification_emails',
    type: 'text',
    multiple: true,
    validations: {
      $each: {
        email,
      },
    },
  },
  notification_times: {
    id: 'notification_times',
    type: 'time',
    multiple: true,
    validations: {
      $each: {
        notificationTime,
      },
    },
  },
  asns: {
    id: 'asns',
    type: 'text',
    multiple: true,
    validations: {
      $each: {
        integer,
        maxValue: maxValue(2 ** 32 - 1),
      },
    },
  },
  fqdns: {
    id: 'fqdns',
    type: 'text',
    multiple: true,
    validations: {
      $each: {
        fqdn,
      },
    },
  },
  ip_networks: {
    id: 'ip_networks',
    type: 'text',
    multiple: true,
    validations: {
      $each: {
        cidr,
      },
    },
  },
  additional_comment: {
    id: 'additional_comment',
    type: 'text',
    multiple: false,
    validations: {
      maxLength: maxLength(4000),
    },
  },
};

for (const crit in criteria) {
  criteria[crit]['textsEN'] = localeEN[crit];
}

export default criteria;
