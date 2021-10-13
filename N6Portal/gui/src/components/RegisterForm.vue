<template>
  <div class="FormGroup">
    <h1>{{ currentLangObj.form_title }}</h1>
    <form @submit.prevent="submit" class="RegisterForm">
      <lang-controls />
      <base-criterion v-model="org_id" :criterion="criteria.org_id" :v="$v.org_id" />
      <base-criterion v-model="actual_name" :criterion="criteria.actual_name"
                      :v="$v.actual_name" />
      <base-criterion v-model="email" :criterion="criteria.email" :v="$v.email" />
      <base-criterion v-model="submitter_title"
                      :criterion="criteria.submitter_title"
                      :v="$v.submitter_title" />
      <base-criterion v-model="submitter_firstname_and_surname"
                      :criterion="criteria.submitter_firstname_and_surname"
                      :v="$v.submitter_firstname_and_surname" />
      <file-criterion v-model="csr"
                      :criterion="criteria.csr"
                      :v="$v.csr"
                      accept=".pem,.csr"
                      @change="csrHandler" />
      <div class="NarrowInputGroups">
        <radio-criterion :criterion="criteria.notification_language"
                         @change="langHandler" />
        <multi-value-group :input-obj="notification_emails"
                           :criterion="criteria.notification_emails"
                           :v_list="$v.notification_emails.$each" />
        <multi-value-group :input-obj="asns"
                           :criterion="criteria.asns"
                           :v_list="$v.asns.$each" />
        <multi-value-group :input-obj="fqdns"
                           :criterion="criteria.fqdns"
                           :v_list="$v.fqdns.$each" />
        <multi-value-group :input-obj="ip_networks"
                           :criterion="criteria.ip_networks"
                           :v_list="$v.ip_networks.$each" />
      </div>
      <input type="submit" :value="currentLangObj.submit" :disabled="!submitButtonEnabled" />
    </form>
  </div>
</template>

<script>

import axios from 'axios';
import { mapGetters, mapState } from 'vuex';
import qs from 'qs';
import { validationMixin } from 'vuelidate';

import CONFIG from '@/config/config.json';
import CRITERIA_CONFIG from '@/config/registerCriteria';
import localeEN from '../locales/EN/register_form.json';
import localePL from '../locales/PL/register_form.json';

import BaseButton from './BaseButton';
import BaseCriterion from './BaseCriterion';
import FileCriterion from './FileCriterion';
import InputActionButtons from './InputActionButtons';
import LangControls from './LangControls';
import MultiCriterion from './MultiCriterion';
import MultiValueGroup from './MultiValueGroup';
import RadioCriterion from './RadioCriterion';

// time in milliseconds when the submit button is disabled after
// an unsuccessful submitting of a form
const INACTIVITY_TIME_AFTER_ERROR = 5000;

export default {
  data() {
    return {
      textsEN: localeEN,
      textsPL: localePL,
      org_id: '',
      actual_name: '',
      email: '',
      submitter_title: '',
      submitter_firstname_and_surname: '',
      csr: '',
      notification_language: 'EN',
      notification_emails: [''],
      asns: [''],
      fqdns: [''],
      ip_networks: [''],
      criteria: CRITERIA_CONFIG,
      submitButtonEnabled: true,
    }
  },
  components: {
    BaseButton,
    BaseCriterion,
    FileCriterion,
    InputActionButtons,
    LangControls,
    MultiCriterion,
    MultiValueGroup,
    RadioCriterion,
  },
  mixins: [validationMixin],
  props: {
    termsAgreed: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    currentLangObj() {
      return this[this.currentLangKey];
    },
    ...mapState('form', [
      'formPending',
    ]),
    ...mapGetters('lang', [
      'currentLangKey',
    ]),
  },
  methods: {
    csrHandler(e) {
      let reader = new FileReader();
      reader.onload = (e) => {
        this.csr = e.target.result;
        this.$v.csr.$touch();
      };
      reader.readAsText(e.target.files[0]);
    },
    isFormReady() {
      return (this.$v.$anyDirty && !this.$v.$anyError);
    },
    getQueryUrl: () => CONFIG.baseURL.concat(CONFIG.APIURLs['register']),
    getRequestPayload() {
      let payload = {};
      for (let key in this.criteria) {
        if (this.criteria[key].hasOwnProperty('multiple') && this.criteria[key].multiple) {
          payload[key] = this.getParsedMultiValues(key);
        } else {
          payload[key] = this[key];
        }
      }
      return payload;
    },
    getParsedMultiValues(key) {
      return this[key].join(',');
    },
    langHandler(e) {
      this.notification_language = e.target.value;
    },
    setFormPending() {
      this.$store.commit('form/setFormPending');
      this.submitButtonEnabled = false;
    },
    setFormSubmitted(success = true) {
      this.$store.commit('form/setFormSubmitted');
      // if submitting of a form was unsuccessful, wait a moment before
      // the submit button is re-enabled
      if (!success) {
        setTimeout(this.enableSubmitButton, INACTIVITY_TIME_AFTER_ERROR);
      }
    },
    enableSubmitButton() {
      this.submitButtonEnabled = true;
    },
    submit() {
      if (!this.termsAgreed) {
        this.$notify({
          group: 'flash',
          type: 'error',
          text: this.currentLangObj.terms_not_agreed,
        });
      } else {
        this.$v.$touch();
        if (this.isFormReady()) {
          this.setFormPending();
          let queryUrl = this.getQueryUrl();
          let payload = this.getRequestPayload();
          axios.create({
            withCredentials: true,
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          })
            .post(queryUrl, qs.stringify(payload))
            .then(
              (resp) => {
                this.setFormSubmitted();
                this.$router.push(`/info/register_success&${this.lang}`);
              })
            .catch(
              (e) => {
                this.setFormSubmitted(false);
                this.$notify({
                  group: 'flash',
                  type: 'error',
                  text: this.currentLangObj.unknown_error,
                });
              }
            );
        } else {
          this.$notify({
            group: 'flash',
            type: 'error',
            text: this.currentLangObj.form_has_errors,
          });
        }
      }
    },
  },
  validations() {
    let validations = {};
    for (const i in this.criteria) {
      if (this.criteria[i].hasOwnProperty('validations')) {
        validations[i] = this.criteria[i].validations;
      } else {
        validations[i] = {};
      }
    }
    return validations;
  },
}
</script>

<style
  lang="scss"
  scoped
>
@import '~@styles/_values.scss';
@import '~@styles/_animations.scss';

h1 {
  font-size: $font-size-extra-large;
}

.LangBox {
  margin-bottom: $margin-medium;
}

.RegisterForm {
  max-width: 800px;
  margin-left: $margin-extra-large;
  margin-top: $margin-large;
}

/deep/ .InputGroup {

  input[type="text"] {
    width: 100%;
    border: 1px $color-grey-light dotted;
    border-radius: 5px;
    padding-left: $padding-small;

    &:focus {
      @include transition(box-shadow, 'long');
      -webkit-box-shadow: inset 10px -14px 30px 3px rgba(0,151,230,0.28);
      -moz-box-shadow: inset 10px -14px 30px 3px rgba(0,151,230,0.28);
      box-shadow: inset 10px -14px 30px 3px rgba(0,151,230,0.28);
      border: 0;
    }
  }
}

.NarrowInputGroups {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;

  /deep/ .InputGroup {
    width: $input-width-medium;
  }
}

/deep/ .ErrorMsgWrapper {
  height: $font-size-large;
  margin-bottom: $margin-extra-extra-extra-small;
}

/deep/ .error-msgs {
  height: inherit;
  display: flex;
  flex-direction: row;
  align-items: center;

  p {
    color: $color-red-dark;
    margin-left: $margin-extra-extra-small;
    margin-right: $margin-extra-small;
    font-size: $font-size-extra-small;
  }
}
</style>
