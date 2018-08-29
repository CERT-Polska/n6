<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/exclamation-triangle';

export default {
  components: {
    Icon,
  },
};
</script>

<template>
  <div class="Error">
    <icon
      name="exclamation-triangle"
      scale="3.8"
      class="Error-Icon"
    />
    <h2 class="Error-Heading">
      Sorry, the server is down.
    </h2>
    <p class='Error-Paragraph'>
      This is a temporary error page.
    </p>
    <p class='Error-Paragraph'>
      Different error pages, adjusted to specific errors, will be implemented soon...
    </p>
  </div>
</template>


<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

.Error {
  display: flex;
  flex-direction: column;
  flex-wrap: nowrap;
  align-items: center;
}

.Error-Icon {
  margin-bottom: $margin-large;
  color: $color-red-light;
}

.Error-Heading {
  margin-bottom: $margin-large;
  font-size: $font-size-large;
  font-weight: 700;
}

.Error-Paragraph {
  & + & {
    margin-top: $margin-small;
  }
}
</style>
