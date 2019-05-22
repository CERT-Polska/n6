<script>
import { VTooltip } from 'v-tooltip';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/trash';
import { validationMixin } from 'vuelidate';
import { mapGetters } from 'vuex';
import isEqual from 'lodash-es/isEqual';

import BaseDatetime from './BaseDatetime';
import BaseFormControl from './BaseFormControl';
import BaseInput from './BaseInput';
import BaseMultiselect from './BaseMultiselect';
import BaseSelect from './BaseSelect';
import validationErrorMessagesMixin from '@/mixins/ValidationErrorMessages';
import CRITERIA_CONFIG from '@/config/searchCriteria';

export default {
  components: {
    BaseDatetime,
    BaseFormControl,
    BaseInput,
    BaseMultiselect,
    BaseSelect,
    Icon,
  },

  directives: {
    'tooltip': VTooltip,
  },

  mixins: [
    validationMixin,
    validationErrorMessagesMixin,
  ],

  props: {
    criterion: {
      type: Object,
      required: true,
      validator: criterion => {
        return ['id', 'value'].every(criterion.hasOwnProperty, criterion);
      },
    },
  },

  data() {
    return {
      criterionConfig: CRITERIA_CONFIG.find(criterion => criterion.id === this.criterion.id),
      inputInfoMessagesShow: false,
      // Value of this criterion as a string as inputted by user
      inputValueString: '',
    };
  },

  computed: {
    ...mapGetters('search', {
      criterionStore: 'criterion',
      statusTouched: 'statusTouched',
    }),

    // Value of this criterion as an object stored in the store
    inputValue: {
      get() {
        return this.criterionStore(this.criterion.id).value;
      },
      set(value) {
        let commitToStore = true;
        let inputValueArray;
        this.inputValueString = value;

        // For text inputs do not commit the user input value, as long as it
        // matches the store value
        if (this.criterionConfig.type === 'text') {
          const storeValue = this.criterionStore(this.criterion.id).value;
          inputValueArray = this.textValueStringToObject(this.inputValueString);
          if (isEqual(storeValue, inputValueArray)) {
            commitToStore = false;
          }
        }

        if (this.criterionConfig.type === 'text') {
          value = inputValueArray;
        }

        if (commitToStore) {
          this.$store.dispatch('search/criterionSet', {
            id: this.criterion.id,
            value,
          });
        }
      },
    },

    inputInfoMessages() {
      if (this.criterionConfig.type === 'text') {
        return ['Use commas to separate multiple values'];
      } else {
        return undefined;
      }
    },

    inputValueValidationErrorMessages() {
      if (this.$v && this.$v.inputValue && this.$v.inputValue.$dirty) {
        return this.validationErrorMessages(this.$v.inputValue);
      } else {
        return undefined;
      }
    },

    showRemoveButton() {
      return !this.criterionConfig.required;
    },
  },

  methods: {
    blurHandler() {
      this.infoMessagesHide();
      this.validationStart();
    },

    focusHandler() {
      this.infoMessagesShow();
      if (!this.$v.inputValue.$invalid) {
        this.validationStop();
      }
    },

    infoMessagesHide() {
      this.inputInfoMessagesShow = false;
    },

    infoMessagesShow() {
      if (this.inputInfoMessages) {
        this.inputInfoMessagesShow = true;
      }
    },

    removeCriterion() {
      this.$store.dispatch('search/criterionRemove', { id: this.criterion.id });
    },

    validationStart() {
      this.$v.inputValue.$touch();
    },

    validationStop() {
      this.$v.inputValue.$reset();
    },

    // Converts comma separated value to array, first normalizing the value
    textValueStringToObject(value) {
      const commasPattern = /\s*,+\s*/g;
      return value
        // Normalize commas and whitespace
        .trim()
        .replace(commasPattern, ',')
        // Split on commas
        .split(',')
        // Remove empty values
        .filter(value => Boolean(value));
    },
  },

  watch: {
    // Validation state needs to be watched and commited to store separately
    // than the value changes, as validation state updates asynchronously after
    // the value changes.
    '$v.inputValue.$invalid': {
      handler: function(newValue, oldValue) {
        this.$store.dispatch('search/criterionSet', {
          id: this.criterion.id,
          valid: !newValue,
        });
      },
      // To commit the initial state
      immediate: true,
    },

    statusTouched: function(newValue, oldValue) {
      if (newValue === true) {
        this.validationStart();
      }
    },
  },

  validations() {
    let validations = {};
    if (this.criterionConfig.validations) {
      validations.inputValue = this.criterionConfig.validations;
    }
    return validations;
  },
};
</script>


<template>
  <base-form-control
    :id="criterionConfig.id"
    class="SearchCriterion"
    :messagesError="inputValueValidationErrorMessages"
    :messagesInfo="inputInfoMessages"
    :messagesInfoShow="inputInfoMessagesShow"
    size="fit"
    orientation="vertical"
  >
    <!-- Control label -->
    <template slot="label">
      <span class="SearchCriterion-Label">
        <span class="SearchCriterion-LabelText">
          {{ criterionConfig.label }}
        </span>
        <!-- Button to remove criterion -->
        <button
          v-if="showRemoveButton"
          aria-label="Remove this criterion"
          class="SearchCriterion-RemoveButton"
          type="button"
          v-tooltip="{
            content: 'Remove this criterion',
            placement: 'top',
          }"
          @click.prevent="removeCriterion"
        >
          <icon
            name="trash"
            scale="1.18"
          />
        </button>
      </span>
    </template>

    <!-- Date time picker -->
    <base-datetime
      v-if="criterionConfig.type === 'datetime'"
      slot="input"
      v-model="inputValue"
      @blur="blurHandler()"
      @focus="focusHandler()"
    />

    <!-- Select -->
    <base-select
      v-else-if="criterionConfig.type === 'select'"
      :id="criterion.id"
      slot="input"
      v-model="inputValue"
      :options="criterionConfig.possibleOptions"
      @blur="blurHandler()"
      @focus="focusHandler()"
    />

    <!-- Multi select -->
    <base-multiselect
      v-else-if="criterionConfig.type === 'multiSelect'"
      :id="criterion.id"
      slot="input"
      v-model="inputValue"
      :options="criterionConfig.possibleOptions"
      track-by="value"
      @blur="blurHandler()"
      @focus="focusHandler()"
    />

    <base-input
      v-else
      :id="criterion.id"
      slot="input"
      v-model="inputValue"
      :type="criterionConfig.type"
      @blur="blurHandler()"
      @focus="focusHandler()"
    />
  </base-form-control>
</template>


<style lang="scss" scoped>
@import '~@styles/_values.scss';

.SearchCriterion {
  // No styles here so far
}

.SearchCriterion-Label {
  // To relatively position the button
  position: relative;
  display: inline-flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
  font-weight: 700;
}

.SearchCriterion-LabelText {
  // No styles here so far
}

.SearchCriterion-RemoveButton {
  position: absolute;
  right: -15px - $margin-extra-extra-small;
}
</style>
