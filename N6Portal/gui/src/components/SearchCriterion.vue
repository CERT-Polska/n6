<script>
import { mapGetters } from 'vuex';
import { VTooltip } from 'v-tooltip';
import BaseDatetime from './BaseDatetime';
import BaseFormControl from './BaseFormControl';
import BaseInput from './BaseInput';
import BaseMultiselect from './BaseMultiselect';
import BaseSelect from './BaseSelect';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/trash';
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
    };
  },

  computed: {
    ...mapGetters('search', {
      criterionStore: 'criterion',
    }),

    inputValue: {
      get() {
        return this.criterionStore(this.criterion.id).value;
      },
      set(value) {
        if (this.criterion.type === 'text') {
          value = this.adjustValue(value);
        }
        this.$store.dispatch('search/criterionSet', { id: this.criterion.id, value });
      },
    },

    showRemoveButton() {
      return !this.criterionConfig.required;
    },
  },

  methods: {
    adjustValue(value) {
      // make it accept text like " , a,b ,  c d ,e ,", then ensure proper commas.
      const pattern1 = new RegExp(' +, +| +,|, +| +', 'g');
      const pattern2 = new RegExp('^,+|,+$', 'g');
      return value.replace(pattern1, ',').replace(pattern2, '');
    },

    removeCriterion() {
      this.$store.dispatch('search/criterionRemove', { id: this.criterion.id });
    },
  },
};
</script>


<template>
  <base-form-control
    :id="criterionConfig.id"
    class="SearchCriterion"
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
      :required="true"
      slot="input"
      v-model="inputValue"
    />

    <!-- Select -->
    <base-select
      v-else-if="criterionConfig.type === 'select'"
      :id="criterion.id"
      required
      slot="input"
      v-model="inputValue"
      :options="criterionConfig.possibleOptions"
    />

    <!-- Multi select -->
    <base-multiselect
      v-else-if="criterionConfig.type === 'multiSelect'"
      :id="criterion.id"
      slot="input"
      v-model="inputValue"
      :options="criterionConfig.possibleOptions"
      track-by="value"
    />

    <base-input
      v-else
      :id="criterion.id"
      required
      slot="input"
      v-model="inputValue"
      :type="criterionConfig.type"
      v-tooltip="{
        content: 'Use commas or spaces to separate multiple values',
        delay: 0,
      }"
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
