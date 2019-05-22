<!-- Truncate single line of text with ellipsis. Show the whole text on click.
-->


<script>
export default {
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
  >
    <!-- Truncated text -->
    <span class="TruncateText-TextTruncated">
      {{ text }}
    </span>

    <!-- Full text displayed on hover -->
    <span class="TruncateText-TextFull">
      {{ text }}
    </span>
  </span>
</template>


<style lang="scss" scoped>
@import '~@styles/_values.scss';

.TruncateText {
  display: block;
  max-width: $size-truncate-text-x;

  &:hover {
    position: relative;

    /* Show full text on hover */
    .TruncateText-TextFull {
      z-index: 1;
      display: block;
      position: absolute;
      top: -1 * $table-cell-padding;
      left: -1 * $table-cell-padding;
      right: -1 * $table-cell-padding;
      padding: $table-cell-padding;
      background-color: $color-background-primary;
      white-space: normal;
      word-break: break-all;
    }
  }
}

.TruncateText-TextTruncated {
  display: block;
  overflow-x: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.TruncateText-TextFull {
  /* Hide until hover */
  display: none;
}
</style>
