<template>
  <div class="ActionButtonsGroup">
    <input-add-button :input-obj="inputObj" />
    <input-delete-button :input-obj="inputObj" />
  </div>
</template>

<script>
import InputAddButton from './InputAddButton';
import InputDeleteButton from './InputDeleteButton';

export default {
  components: {
    InputAddButton,
    InputDeleteButton,
  },
  props: ['inputObj'],
};
</script>

<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

</style>
