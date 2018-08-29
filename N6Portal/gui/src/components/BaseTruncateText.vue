<!-- Truncate single line of text with ellipsis. Show the whole text on click.
-->


<script>
import { VTooltip } from 'v-tooltip';

export default {
  directives: {
    'tooltip': VTooltip,
  },

  props: {
    text: {
      type: String,
      required: true,
    },
  },

  data() {
    return {
      textExpanded: false,
    };
  },

  computed: {
    expandedStateClass() {
      return {
        'TruncateText--IsExpanded': this.textExpanded,
      };
    },
  },

  methods: {
    textExpand() {
      this.textExpanded = !this.textExpanded;
    },
  },
};
</script>


<template>
  <span
    v-if="text"
    class="TruncateText"
    :class="expandedStateClass"
    v-tooltip="{
      content: text,
      placement: 'bottom',
      delay: 0,
    }"
    @click="textExpand()"
  >
    {{ text }}
  </span>
</template>


<style lang="scss" scoped>
@import '~@styles/_values.scss';

.TruncateText {
  display: block;
  max-width: $size-truncate-text-x;
  overflow-x: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  &:hover {
    cursor: pointer;
  }

  &.TruncateText--IsExpanded {
    overflow-x: visible;
    white-space: normal;
    word-break: break-all;
  }
}
</style>
