<template>
<!--  <base-button type="button" @click="onClick">-->
<!--    <icon-->
<!--      name="minus"-->
<!--      scale="0.8"-->
<!--    />-->
<!--  </base-button>-->
  <a @click.prevent="onClick" class="ActionButton">
    <icon
      name="minus"
      scale="0.8"
    />
  </a>
</template>

<script>
import 'vue-awesome/icons/minus';

import InputActionButton from './InputActionButton';

export default {
  extends: InputActionButton,
  methods: {
    onClick(e) {
      if (this.inputObj.length > 1) {
        this.inputObj.pop();
      } else if (this.inputObj.length === 1 && this.inputObj[0]) {
        // if it is last remaining input and it is not empty,
        // clear its value when clicking minus
        this.inputObj.pop();
        this.inputObj[0] = '';
      } else {
        this.$notify({
          group: 'flash',
          type: 'error',
          text: this.currentLangObj.errorMessages.remove_last_input_msg,
        });
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
  color: $color-red-dark;

  &:hover {
    color: $color-yellow-dark;
  }
}
</style>
