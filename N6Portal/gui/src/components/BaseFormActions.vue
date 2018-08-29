<template>
  <div class="FormActions">
    <slot />
  </div>
</template>


<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

.FormActions {
  margin-top: $margin-medium;

  &:first-child {
    margin-top: 0;
  }
}
</style>
