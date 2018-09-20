<script>
export default {
  props: {
    type: {
      type: String,
      required: true,
    },
    // Used by v-model declared on the component
    value: {
      required: true,
    },
  },

  computed: {
    listeners() {
      return {
        ...this.$listeners,
        input: event => this.$emit('input', event.target.value),
        change: event => this.$emit('change', event.target.value),
      };
    },
  },
};
</script>


<template>
  <input
    class="Input"
    :type="type"
    :value="value"
    v-on="listeners"
  />
</template>


<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

.Input {
  border-radius: $border-radius;
  border: 1px solid $color-grey-light;
  padding: $padding-small $padding-extra-small;
  height: $size-input-y;
}
</style>
