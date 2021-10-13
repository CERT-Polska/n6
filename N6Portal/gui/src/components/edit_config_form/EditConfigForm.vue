<template>
  <div class="FormGroup">
    <h1>Edit organization settings</h1>
    <form @submit.prevent="submit"
          :class="{inactive: !dataLoaded}"
          class="EditConfigForm"
          @click="warnOnEdit"
    >
      <base-field v-model="org_id" :criterion="criteria.org_id"
                  :v="$v.org_id" @valueChange="changeHandler"
                  :disabled="true"
      />
      <base-field v-model="actual_name" :criterion="criteria.actual_name"
                  :v="$v.actual_name" @valueChange="changeHandler" />
      <checkbox-field :checked="notification_enabled"
                      :criterion="criteria.notification_enabled"
                      @valueChange="checkboxHandler"
      />
      <div class="NarrowInputGroups">
        <radio-field v-model="notification_language"
                     :criterion="criteria.notification_language"
                     @valueChange="radioHandler"
                     :value="notification_language"
        />
        <multi-value-field-group :input-obj="notification_emails"
                                 :criterion="criteria.notification_emails"
                                 :v_list="$v.notification_emails.$each"
                                 @valueChange="changeHandler"
        />
        <multi-value-field-group :input-obj="notification_times"
                                 :criterion="criteria.notification_times"
                                 :v_list="$v.notification_times.$each"
                                 @valueChange="changeHandler"
        />
        <multi-value-field-group :input-obj="asns"
                                 :criterion="criteria.asns"
                                 :v_list="$v.asns.$each"
                                 @valueChange="changeHandler"
        />
        <multi-value-field-group :input-obj="fqdns"
                                 :criterion="criteria.fqdns"
                                 :v_list="$v.fqdns.$each"
                                 @valueChange="changeHandler"
        />
        <multi-value-field-group :input-obj="ip_networks"
                                 :criterion="criteria.ip_networks"
                                 :v_list="$v.ip_networks.$each"
                                 @valueChange="changeHandler"
        />
      </div>
      <div class="TallInputGroups">
      <text-area-field v-model="additional_comment" :criterion="criteria.additional_comment"
                      :v="$v.additional_comment" @valueChange="changeHandler"
      />
      </div>
      <base-button type="submit" value="Submit" :disabled="!submitButtonEnabled || formDisabled">
        Submit
      </base-button>
      <base-button
        type="button"
        class="ResetButton"
        :disabled="!isFormUpdated || formDisabled"
        @click="resetFormHandler"
      >
        Reset form
      </base-button>
    </form>
  </div>
</template>

<script>

import axios from 'axios';
import { remove } from 'lodash-es';
import { mapGetters, mapState } from 'vuex';
import qs from 'qs';
import { validationMixin } from 'vuelidate';

import CONFIG from '@/config/config.json';
import CRITERIA_CONFIG from '@/config/userConfigCriteria';

import BaseButton from '../BaseButton';
import BaseField from './BaseField';
import CheckboxField from './CheckboxField';
import MultiValueFieldGroup from './MultiValueFieldGroup';
import RadioField from './RadioField';
import TextAreaField from './TextAreaField';
import LangSetMixin from '@/mixins/LangSetMixin';

// time in milliseconds when the submit button is disabled after
// an unsuccessful submitting of a form
const INACTIVITY_TIME_AFTER_ERROR = 5000;

const EDITABLE_FIELDS = [
  'actual_name',
  'asns',
  'fqdns',
  'ip_networks',
  'notification_enabled',
  'notification_language',
  'notification_emails',
  'notification_times',
];
const MULTI_VALUE_FIELDS = [
  'asns',
  'fqdns',
  'ip_networks',
  'notification_emails',
  'notification_times',
];
const OTHER_RESPONSE_FIELDS = [
  'org_id',
  'post_accepted',
  'update_info',
];

export default {
  data() {
    return {
      org_id: '',
      actual_name: '',
      notification_enabled: false,
      notification_language: '',
      notification_emails: [''],
      notification_times: [''],
      asns: [''],
      fqdns: [''],
      ip_networks: [''],
      additional_comment: '',
      updated_fields: {},
      criteria: CRITERIA_CONFIG,
      submitButtonEnabled: true,
      messages: {
        updatePending: 'Waiting for the last changes to be accepted.<br>' +
                       'Until then, the settings cannot be changed',
        onEdit: 'User settings changes are pending, the form is currently disabled',
        unknownError: 'Something went wrong. Could not send the form. ' +
          'Please try again in a moment',
        formHasErrors: 'Your settings form contains errors',
        formUnchanged: 'There are no changes in the settings',
        postNotAccepted: 'Your request has not been accepted',
      },
    }
  },
  components: {
    BaseButton,
    BaseField,
    CheckboxField,
    MultiValueFieldGroup,
    RadioField,
    TextAreaField,
  },
  mixins: [LangSetMixin, validationMixin],
  provide() {
    return {
      areArraysEqual: this._areArraysEqual,
    }
  },
  beforeMount() {
    // temporarily support English only
    this.storeLang('en', true);
  },
  mounted() {
    this.$store.commit('form/setDataLoading');
    // make sure there are no residue updated fields in VueX store
    // from the previous submission of the form
    this._resetUpdatedFields();
    this.fetchFormData()
      .then(() => {
        this.$store.commit('form/setDataReady');
      })
      .catch(e => {
        this.$notify({
          group: 'flash',
          type: 'error',
          text: e,
          duration: -1,
        });
      });
  },
  computed: {
    ...mapGetters('form', [
      'isFormUpdated',
    ]),
    ...mapState('form', [
      'dataLoaded',
      'formDisabled',
      'originalFields',
      'updatedFields',
    ]),
  },
  methods: {
    _validateResponseKeys(response) {
      // checks whether the response JSON document has all of the
      // required fields
      for (const field of EDITABLE_FIELDS.concat(OTHER_RESPONSE_FIELDS)) {
        if (!response.hasOwnProperty(field)) {
          return false;
        }
      }
      return true;
    },
    _convertIfNotArrayOfStrings(values) {
      // converts integer items of array types of response fields
      // to strings
      let result = [];
      for (const val of values) {
        if (Number.isInteger(val)) {
          result.push(val.toString());
        } else {
          result.push(val);
        }
      }
      return result;
    },
    _copyField(payload, fieldName, commitName) {
      if (MULTI_VALUE_FIELDS.includes(fieldName)) {
        let value;
        // there might be a case, when the original value of
        // a multi-value field is null
        if (Array.isArray(payload[fieldName])) {
          value = this._convertIfNotArrayOfStrings(payload[fieldName]);
        } else {
          value = [];
        }
        this.$store.commit(commitName, {
          fieldName: fieldName,
          value: value.slice(),
        });
        this[fieldName] = value.slice();
      } else {
        this.$store.commit(commitName, {
          fieldName: fieldName,
          value: payload[fieldName],
        });
        this[fieldName] = payload[fieldName];
      }
    },
    _copyEditablePayload(payload) {
      // copy fields from payload to originalFields and update input
      // values
      for (const field of EDITABLE_FIELDS) {
        this._copyField(payload, field, 'form/addOriginalField');
      }
      // add the field to `originalFields`, which should not have
      // its value from response payload, but its value to compare
      // with should be an empty string
      this.$store.commit('form/addOriginalField', {
        fieldName: 'additional_comment',
        value: '',
      });
      // the `org_id` field is not an editable field, so only set
      // the attribute, so the input shows its value
      this.org_id = payload.org_id;
    },
    _copyUpdatedPayload(updatedFields) {
      // copy fields from payload to updatedFields and update input
      // values, only if the settings change is pending
      for (const field of EDITABLE_FIELDS.concat('additional_comment')) {
        if (updatedFields.hasOwnProperty(field)) {
          this._copyField(updatedFields, field, 'form/addUpdatedField');
        }
      }
    },
    _resetUpdatedFields() {
      for (const fieldName in this.updatedFields) {
        this.$store.commit('form/deleteUpdatedField', fieldName);
      }
    },
    _areArraysEqual(a, b) {
      if (a.length !== b.length) {
        return false;
      }
      for (const el of a) {
        if (!b.includes(el)) {
          return false;
        }
      }
      return true;
    },
    _doCommitChange(fieldName, value, origValue) {
      if (value !== origValue) {
        this.$store.commit('form/addUpdatedField', {
          fieldName: fieldName,
          value: value,
        });
      } else {
        // condition when input value is equal to original value,
        // so the field is deleted from the updatedFields
        this.$store.commit('form/deleteUpdatedField', fieldName);
      }
    },
    _doCommitArrayChange(fieldName, value, origValue) {
      if (!this._areArraysEqual(value, origValue)) {
        // remember to use a copy (slice() method) of an array, so
        // the copy is set as a key of the VueX state object; otherwise
        // the reference would have been set and mutating one of the
        // arrays would mutate both of them
        this.$store.commit('form/addUpdatedField', {
          fieldName: fieldName,
          value: value.slice(),
        });
      } else {
        this.$store.commit('form/deleteUpdatedField', fieldName);
      }
    },
    _getNewArrayWithValOnIndex(value, index, target) {
      // return a new array with the value pushed onto specific index
      let targetCopy = target.slice();
      if (!targetCopy.length || (targetCopy.length === 1 && targetCopy[0] === '')) {
        // in case the target array contains only an empty string,
        // just replace it with the value, so concatenating the slices
        // does not result in an array containing the value and
        // an empty string
        targetCopy[0] = value;
        return targetCopy;
      }
      // make a room for the value
      let firstPart = targetCopy.slice(0, index);
      let remainingPart = targetCopy.slice(index);
      return firstPart.concat(value).concat(remainingPart);
    },
    _updateUpdatedFields(actionType, fieldName, value, origValue, index = null) {
      if (actionType === 'change') {
        if (Array.isArray(value)) {
          this._doCommitArrayChange(fieldName, value, origValue);
        } else {
          this._doCommitChange(fieldName, value, origValue);
        }
      } else if (actionType === 'undo') {
        this[fieldName] = origValue;
        this.$store.commit('form/deleteUpdatedField', fieldName);
      } else if (actionType === 'revert' && index !== null && Array.isArray(origValue)) {
        // the type of action that will revert a value deleted from
        // a multi-field input
        let resultArray = this._getNewArrayWithValOnIndex(value,
          index,
          this.updatedFields[fieldName]);
        this[fieldName] = resultArray;
        this._doCommitArrayChange(fieldName, resultArray, origValue);
      }
    },
    changeHandler(e) {
      let origValue;
      if (e.criterionType === 'array' || Array.isArray(e.value)) {
        origValue = this.originalFields[e.id].slice();
      } else {
        origValue = this.originalFields[e.id];
      }
      if (e.type === 'change' || e.type === 'undo') {
        this._updateUpdatedFields(e.type, e.id, e.value, origValue);
      } else if (e.type === 'revert') {
        this._updateUpdatedFields(e.type, e.id, e.value, origValue, e.index);
      }
    },
    radioHandler(e) {
      let origValue = this.originalFields.notification_language;
      if (origValue) {
        origValue = origValue.toUpperCase();
      }
      if (e.type === 'change') {
        let newValue = e.value.toUpperCase();
        this.notification_language = newValue;
        this._updateUpdatedFields(e.type, e.id, newValue, origValue);
      } else if (e.type === 'undo') {
        this._updateUpdatedFields(e.type, e.id, null, origValue);
      }
    },
    checkboxHandler(e) {
      this.notification_enabled = !this.notification_enabled;
      this._updateUpdatedFields(
        e.type,
        e.id,
        this.notification_enabled,
        this.originalFields.notification_enabled,
      );
    },
    resetFormHandler(e) {
      // reset all the fields
      if (!this.formDisabled) {
        for (const fieldName in this.updatedFields) {
          let origValue;
          if (Array.isArray(this.originalFields[fieldName])) {
            origValue = this.originalFields[fieldName].slice();
          } else {
            origValue = this.originalFields[fieldName];
          }
          this._updateUpdatedFields('undo',
            fieldName,
            null,
            origValue);
        }
      }
    },
    warnOnEdit(e) {
      if (this.formDisabled) {
        this.$notify({
          group: 'flash',
          type: 'warn',
          text: this.messages.onEdit,
        });
      }
    },
    fetchFormData() {
      return new Promise((resolve, reject) => {
        axios
          .create({
            withCredentials: true,
          })
          .get(this.getQueryUrl())
          .then(response => {
            if (!!response && !!response.data) {
              if (!this._validateResponseKeys(response.data)) {
                throw new Error('Server has returned an incomplete response');
              }
              this._copyEditablePayload(response.data);
              if (response.data.update_info) {
                this._copyUpdatedPayload(response.data.update_info);
                this.$store.commit('form/setFormDisabled');
                this.$notify({
                  group: 'flash',
                  text: this.messages.updatePending,
                  duration: 5000,
                });
              }
              resolve(response.data);
            } else {
              throw new Error('Failed to fetch user settings');
            }
          })
          .catch(e => {
            reject(e);
          });
      });
    },
    isFormReady() {
      return (this.$v.$anyDirty && !this.$v.$anyError);
    },
    isUpdatedFieldsEmpty() {
      // the form is assumed not to be updated if it does not have any
      // properties, or its only property is 'additional_comment',
      // which is an additional field and does not introduce any
      // changes in the settings (in both cases user should not be
      // allowed to submit the form)
      return !this.isFormUpdated ||
        (Object.keys(this.updatedFields).length === 1 && this.updatedFields.additional_comment);
    },
    getQueryUrl: () => CONFIG.baseURL.concat(CONFIG.APIURLs['settings']),
    getRequestPayload() {
      let payload = {};
      for (const fieldName in this.updatedFields) {
        if (this.criteria[fieldName].multiple) {
          payload[fieldName] = this.getParsedMultiValues(this.updatedFields[fieldName].slice());
        } else {
          payload[fieldName] = this.updatedFields[fieldName];
        }
      }
      return payload;
    },
    getParsedMultiValues(field) {
      // remove empty array elements first, but do not remove the field
      // if it contains only empty fields, because its presence means
      // that the field should be updated
      remove(field, n => {
        return !n;
      });
      return field.join(',');
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
      this.$v.$touch();
      if (!this.isFormReady()) {
        this.$notify({
          group: 'flash',
          type: 'error',
          text: this.messages.formHasErrors,
        });
      } else if (this.isUpdatedFieldsEmpty()) {
        this.$notify({
          group: 'flash',
          type: 'error',
          text: this.messages.formUnchanged,
        });
      } else {
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
              if (resp.data && resp.data.post_accepted) {
                this.setFormSubmitted();
                this._resetUpdatedFields();
                this.$router.push(`/info/settings_change_pending&en`);
              } else {
                this.setFormSubmitted(false);
                this.$notify({
                  group: 'flash',
                  type: 'error',
                  text: this.messages.postNotAccepted,
                });
              }
            })
          .catch(
            (e) => {
              this.setFormSubmitted(false);
              this.$notify({
                group: 'flash',
                type: 'error',
                text: this.messages.unknownError,
              });
            }
          );
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
@import '~@styles/base.scss';

h1 {
  font-size: $font-size-extra-large;
}

.LangBox {
  margin-bottom: $margin-medium;
}

.EditConfigForm {
  max-width: 800px;
  margin-left: $margin-extra-large;
  margin-top: $margin-large;
}

/deep/ .InputGroup {

  // the property below is used, so the 'undo' button with an absolute
  // position is limited to element's area
  position: relative;

  input[type="text"], input[type="time"] {
    width: 100%;
    border: 1px $color-grey-light dotted;
    border-radius: 5px;
    padding-left: $padding-small;
    padding-right: 40px;

    &:focus {
      @include transition(box-shadow, 'long');
      -webkit-box-shadow: inset 10px -14px 30px 3px rgba(0,151,230,0.28);
      -moz-box-shadow: inset 10px -14px 30px 3px rgba(0,151,230,0.28);
      box-shadow: inset 10px -14px 30px 3px rgba(0,151,230,0.28);
      border: 0;
    }
  }

  input[readonly], textarea[readonly] {
    // unify colors between read-only 'time' and other types
    // of inputs
    color: $input-readonly-color;
  }

  .InputGroup--UndoButton {
    position: absolute;
    right: 10px;
    top: 34.6px;
    display: none;
  }

  .InputGroup--UndoButton-active {
    display: block;
    opacity: 0.5;

    &:hover {
      @include transition(opacity, 'regular');
      opacity: 1;
    }
  }
}

/deep/ .EditedInput {
    @include transition(box-shadow, 'long');
    @include EditedInputGradient;
    border: 1px $input-edited-border-color solid !important;
}

.NarrowInputGroups {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;

  /deep/ .InputGroup {
    width: $input-width-medium;

    input[type="text"] {
      width: $input-width-medium - 2px;
    }

    input[type="time"] {
      width: $input-width--time;
      padding: 10px;

      &:focus {
        border: none;
      }
    }
  }
}

.TallInputGroups {
  /deep/ .InputGroup {
    textarea {
      width: 100%;
      height: $input-height-large;
    }
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
