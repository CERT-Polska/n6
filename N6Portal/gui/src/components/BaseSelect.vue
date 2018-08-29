<script>
import omit from 'lodash-es/omit';

export default {
  props: {
    // Array of objects { value, label }
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
    // Used by v-model declared on the component
    value: {
      required: true,
    },
  },

  computed: {
    listeners() {
      // Delete input and change handlers so that they don't capture native
      // input and change events. They will still fire, but triggered by
      // custom input and change events emitted in the valueCopy setter.
      return omit(this.$listeners, ['change', 'input']);
    },

    // Needed to use v-model (as you shouldn't bind a prop to v-model) to
    // preserve value type
    valueCopy: {
      get() {
        return this.value;
      },
      set(value) {
        // input and change events that are fired instead of native browser
        // ones.
        this.$emit('input', value);
        this.$emit('change', value);
      },
    },

  },
};
</script>


<template>
  <select
    v-model="valueCopy"
    v-bind="$attrs"
    v-on="listeners"
    class="BaseSelect"
  >
    <option
      v-for="option in options"
      :value="option.value"
    >
      {{ option.label }}
    </option>
  </select>
</template>


<style lang="scss" scoped>
@import '~@styles/_values.scss';

.BaseSelect {
  height: $size-input-y;
}
</style>
