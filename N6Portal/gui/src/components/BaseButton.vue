<script>
import { VTooltip } from 'v-tooltip';

export default {
  directives: {
    'tooltip': VTooltip,
  },

  props: {
    role: {
      type: String,
      required: false,
      default: 'secondary',
      validator: value => {
        let allowedValues = ['primary', 'secondary', 'secondary-alternate'];
        return allowedValues.includes(value);
      },
    },
    tooltip: {
      type: String,
    },
  },
};
</script>


<template>
  <button
    :class="{
      'Button--Primary': role === 'primary',
      'Button--Secondary': role === 'secondary',
      'Button--SecondaryAlternate': role === 'secondary-alternate',
    }"
    v-bind="$attrs"
    v-on="$listeners"
    v-tooltip="tooltip"
  >
    <slot />
  </button>
</template>


<style
  scoped
  lang="scss"
>
@import '~@styles/_animations.scss';
@import '~@styles/_values.scss';

%Button {
  @include transition((background-color, color, border-color));

  align-items: center;
  border-width: $border-width;
  border-style: solid;
  border-radius: $border-radius;
  height: $size-input-y;
  padding-left: $padding-small;
  padding-right: $padding-small;

  &:focus {
    border-color: $color-black;
    box-shadow: 0 0 1px 2px $color-grey-dark;

    // Disable default Firefox focus outline
    &::-moz-focus-inner {
      border: none;
    }
  }
}

.Button--Primary {
  @extend %Button;

  border-color: $color-navy-dark;
  color: $color-white;
  background-color: $color-blue-light;

  &:hover {
    border-color: $color-blue-dark;
    background-color: $color-blue-dark;
  }
}

.Button--Secondary {
  @extend %Button;

  border-color: $color-grey-light;
  color: $color-grey-extra-dark;
  background-color: $color-grey-extra-light;

  &:hover {
    color: $color-white;
    background-color: $color-grey-light;
  }
}

.Button--SecondaryAlternate {
  @extend %Button;

  border-color: $color-grey-light;
  color: $color-grey-extra-dark;
  background-color: $color-grey-extra-extra-light;

  &:hover {
    color: $color-white;
    background-color: $color-grey-light;
  }
}
</style>
