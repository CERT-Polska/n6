<!-- Wrapper for multiselect component -->


<script>
import vueSelect from 'vue-select';
import isEqual from 'lodash-es/isEqual';
import omit from 'lodash-es/omit';

export default {
  components: {
    vueSelect,
  },

  props: {
    // Used by v-model
    value: {
      type: Array,
      required: true,
      default: () => [],
    },
    options: {
      type: Array,
      required: true,
      validator: options => {
        let requiredProperties = ['value', 'label'];
        return options.every(option =>
          requiredProperties.every(option.hasOwnProperty, option)
        );
      },
    },
  },

  computed: {
    listeners() {
      // Delete input and change handlers so that they don't capture native
      // input and change events. They will still fire, but triggered by
      // custom input and change events emitted in the localModel setter.
      return omit(this.$listeners, ['input', 'change']);
    },

    // Needed to work around the fact that vue-select component sets the value of
    // the select incorrectly - instead of setting it to array of option values
    // (option.value property), it sets it to array of option objects
    localModel: {
      get() {
        return this.valueInputTransformed();
      },
      set(valueNew) {
        // Using valueInputTransformed() (instead of this.localModel) to get
        // the real input value, as vue-select modifies the array returned by
        // getter for localModel, while the getter is cached and will be not
        // run until valueInputTransformed changes.
        //
        // isEqual is a deep comparison (by values, not by references). The
        // comparison needs to be made, as the setter is also run after changing
        // the input value and if events are emitted every time the setter is
        // run, endless loop of events occur.
        if (!isEqual(valueNew, this.valueInputTransformed())) {
          let valueOutput = valueNew ? valueNew.map(v => v.value) : [];
          this.$emit('input', valueOutput);
          this.$emit('change', valueOutput);
        }
      },
    },
  },

  methods: {
    // Transforms the input value (array of values) to the format used by
    // vue-select (array of objects with 'value' property) using the exact objects
    // from options prop.
    valueInputTransformed() {
      let valueInput = this.value ? this.value : [];
      return valueInput.map(optionValue =>
        this.options.find(option => option.value === optionValue)
      );
    },
  },
};
</script>


<template>
  <vue-select
    v-model="localModel"
    multiple
    :options="options"
    placeholder="Click to add..."
    v-bind="$attrs"
    v-on="listeners"
  />
</template>


<style lang="scss" scoped>
@import '~@styles/_values.scss';

.v-select {

  /deep/ .dropdown-toggle {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    position: relative;
    border-radius: $border-radius;
    min-width: 250px;
    height: $size-input-y;
    padding-left: $padding-extra-extra-extra-small;
    padding-right: 31px;

    & > input {
      z-index: 0;
      position: absolute;
      top: 0;
      bottom: 0;
      left: 0;
      right: 0;
      max-width: unset;
      width: 100% !important;
    }

    & > .selected-tag {
      display: flex;
      flex-direction: row;
      flex-wrap: nowrap;
      align-items: center;
      z-index: 1;
      position: relative;
      margin: 0;
      border-radius: $border-radius;

      & + .selected-tag {
        margin-left: $margin-extra-extra-extra-small;
      }

      & > .close {
        margin: $margin-extra-extra-extra-small;
      }
    }

    & > .open-indicator {
      bottom: 3px;
    }
  }

  &.open /deep/ .dropdown-toggle > .open-indicator {
    bottom: -1px;
  }
}
</style>
