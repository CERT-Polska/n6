<template>
  <div class="InputLabel">
    <label v-bind:for="idVal">{{ labelVal }}</label>
    <div class="InputLabel-Elements">
      <slot></slot>
      <icon
        v-if="tooltipText"
        v-tooltip="{
          content: tooltipText,
          trigger: 'hover click',
        }"
        name="question-circle"
        scale="1"
        class="Question-Icon"
      />
    </div>
  </div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/question-circle';
import { VTooltip } from 'v-tooltip';

export default {
  components: {
    Icon,
  },
  directives: {
    'tooltip': VTooltip,
  },
  props: ['labelVal', 'idVal', 'tooltipText'],
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

.InputLabel-Elements {
  float: right;
  display: flex;

  * {
    margin-left: $margin-small;
  }
}

.Question-Icon {
  color: $color-blue-light;

  &:hover {
    color: $color-yellow-light;
  }
}
</style>
