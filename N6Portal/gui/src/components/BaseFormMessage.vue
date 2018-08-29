<template>
  <p class="BaseFormMessage">
    <slot />
  </p>
</template>


<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

.BaseFormMessage {
  margin-top: $margin-large;

  &:first-child {
    margin-top: 0;
  }
}
</style>
