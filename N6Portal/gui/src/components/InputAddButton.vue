<template>
  <a @click.prevent="onClick" class="ActionButton">
    <icon
      name="plus"
      :scale="iconScale"
    />
  </a>
</template>

<script>
import 'vue-awesome/icons/plus';

import InputActionButton from './InputActionButton';

export default {
  extends: InputActionButton,
  props: {
    inputObj: {
      type: Array,
      required: true,
    },
    iconScale: {
      type: Number,
      default: 0.8,
    },
  },
  methods: {
    onClick(e) {
      if (!this.checkIfFormDisabled() && this.inputObj[this.inputObj.length - 1] !== '') {
        // do not add new empty field if the previous one is empty
        if (this.inputObj.length < this.multivaluedInputLimit) {
          this.inputObj.push('');
        } else {
          this.$notify({
            group: 'flash',
            type: 'error',
            text: this.currentLangObj.errorMessages.multivalued_field_limit_msg,
          });
        }
      }
    },
  },
};
</script>

<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

.ActionButton {
  color: $color-green-dark;
  margin-right: $margin-extra-small;

  &:hover {
    color: $color-yellow-dark;
  }
}
</style>
