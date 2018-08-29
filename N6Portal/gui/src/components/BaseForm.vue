<script>
export default {
  props: {
    errorMessage: String,
  },
};
</script>


<template>
  <form
    class="Form"
    v-on="$listeners"
  >
    <p
      v-if="errorMessage"
      class="Form-Error"
    >
      {{ errorMessage }}
    </p>
    <slot />
  </form>
</template>

<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

.Form {
  display: flex;
  flex-direction: column;
  flex-wrap: nowrap;
  align-items: center;
}

.Form-Error {
  margin-bottom: $margin-medium;
  color: $color-red-light;
}
</style>
