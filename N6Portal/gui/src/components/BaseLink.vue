<script>
import { VTooltip } from 'v-tooltip';

export default {
  directives: {
    'tooltip': VTooltip,
  },

  props: {
    // `href` is likely to be expected here, but as this component not always
    // uses <a> tag, it's cleaner to optionally include it in `v-bind="$attrs"`.
    tooltip: {
      type: String,
      required: false,
    },
    // Tag to be used for the link, as the link can be a <button> or
    // <router-link> in addition to default <a>.
    tag: {
      type: String,
      default: 'a',
      validator: value => ['a', 'button', 'router-link'].includes(value),
    },
  },
};
</script>


<template>
  <component
    :is="tag"
    class="Link"
    v-bind="$attrs"
    v-on="$listeners"
    v-tooltip="{
      content: tooltip,
      disabled: Boolean(tooltip),
    }"
  >
    <slot />
  </component>
</template>


<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

.Link {
  color: $color-blue-dark;
  text-decoration: underline;

  &:hover {
    color: $color-blue-light;
  }
}
</style>
