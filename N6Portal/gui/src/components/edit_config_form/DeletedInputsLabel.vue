<template>
  <div class="Deleted-InputLabel">
    <label>{{ title }}</label>
    <div class="InputLabel-Elements">
      <slot></slot>
    </div>
  </div>
</template>

<script>
import InputLabel from '../InputLabel';

export default {
  data() {
    return {
      title: 'Deleted values in ' + this.labelVal,
    }
  },
  extends: InputLabel,
};
</script>

<style
  scoped
  lang="scss"
>
  @import '~@styles/_values.scss';

  .InputLabel {
    font-size: $font-size-small;
    font-weight: bold;
    margin-bottom: $margin-extra-extra-extra-small + 1px;
    max-width: $input-width-medium;
    padding: $padding-extra-extra-small;
    color: $color-grey-extra-dark;
    background: $color-grey-extra-light;
    border-radius: 5px;
  }

  .Deleted-InputLabel {
    @extend .InputLabel;
    background: #8c8a7e;
    color: #ffffff;
  }
</style>
