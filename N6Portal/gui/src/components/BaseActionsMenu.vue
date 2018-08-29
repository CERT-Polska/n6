<!-- Menu with list of actions
-->


<script>
export default {
  props: {
    // List of actions of format { text, callback }
    actions: {
      type: Array,
      required: true,
      validator: actions => {
        let requiredProperties = ['text', 'callback'];
        return actions.every(action => {
          return requiredProperties.every(action.hasOwnProperty, action)
        });
      },
    },
  },

  methods: {
    invokeCallback(callback, event) {
      callback(event);
    },
  },
};
</script>


<template>
  <ul class="ActionsMenu">
    <li
      v-for="action in actions"
      :key="action.text"
      @click="invokeCallback(action.callback, $event)"
      class="ActionsMenu-Action"
    >
      {{ action.text }}
    </li>
  </ul>
</template>


<style lang="scss" scoped>
@import '~@styles/_values.scss';

.ActionsMenu {
  display: flex;
  flex-direction: column;
  flex-wrap: nowrap;
}

.ActionsMenu-Action {
  $spacing-y: $margin-extra-small;
  $padding-y: $spacing-y / 2;

  padding: ($spacing-y / 2) $padding-extra-small;
  cursor: pointer;

  &:hover {
    color: $color-white;
    background-color: $color-blue-light;
  }

  &:first-child {
    padding-top: $padding-y;
  }

  &:last-child {
    padding-bottom: $padding-y;
  }
}
</style>
