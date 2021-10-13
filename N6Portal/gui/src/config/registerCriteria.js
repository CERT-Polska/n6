import localeEN from '../locales/EN/register_form_fields.json';
import localePL from '../locales/PL/register_form_fields.json';

import {
  email,
  maxValue,
  integer,
  required,
} from 'vuelidate/lib/validators';

import {
  cidr,
  fqdn,
  validFile,
  orgId,
} from '../helpers/validators';

let criteria = {
  org_id: {
    id: 'org_id',
    type: 'text',
    validations: {
      required,
      orgId,
    },
  },
  actual_name: {
    id: 'actual_name',
    type: 'text',
    validations: {
      required,
    },
  },
  email: {
    id: 'email',
    type: 'text',
    validations: {
      required,
      email,
    },
  },
  submitter_title: {
    id: 'submitter_title',
    type: 'text',
    validations: {
      required,
    },
  },
  submitter_firstname_and_surname: {
    id: 'submitter_firstname_and_surname',
    type: 'text',
    required: true,
    validations: {
      required,
    },
  },
  csr: {
    label: 'CSR file',
    id: 'csr',
    type: 'file',
    validations: {
      validFile,
    },
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
};

// append every field's property with matching `textsEN` and `textsPL`
// properties from ../locales/<LANG>/register_form_fields.json,
// containing localized labels and descriptions
for (const crit in criteria) {
  criteria[crit].textsPL = localePL[crit];
  criteria[crit].textsEN = localeEN[crit];
}

export default criteria;
