<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/exclamation-triangle';

export default {
  components: {
    Icon,
  },

  props: {
    errorCode: {
      type: [String, Number],
    },
  },

  data() {
    return {
      errorMessages: {
        500: {
          heading: 'Sorry, the server is down',
          description: 'There was an unexpected problem on the server side.',
        },
        404: {
          heading: 'Page not found',
          description: 'It seems that the page you tried to access doesn\'t exist.',
        },
        default: {
          heading: 'Unexpected error',
          description: 'Some unexpected error occured',
        },
      },
    };
  },

  computed: {
    errorHeading: function() {
      return this.errorData(this.errorCode).heading;
    },
    errorDescription: function() {
      return this.errorData(this.errorCode).description;
    },
  },

  methods: {
    errorData: function(errorCode) {
      // We could cache the result and compute again if the errorCode changed
      if (errorCode === undefined ||
        !this.$data.errorMessages.hasOwnProperty(errorCode.toString())) {
        return this.$data.errorMessages.default;
      }
      return this.$data.errorMessages[errorCode];
    },
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
      {{ errorHeading }}
    </h2>
    <p class='Error-Paragraph'>
      {{ errorDescription }}
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
