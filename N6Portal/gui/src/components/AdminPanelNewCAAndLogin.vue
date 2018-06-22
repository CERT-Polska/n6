<script>
export default {
  data() {
    return {
      form: {
        email: '',
        name: '',
      },
      show: true,
    };
  },
  methods: {
    onSubmit(evt) {
      evt.preventDefault();
    },
    onReset(evt) {
    },
  },
};
</script>


<template>
  <b-form
    v-if="show"
    @submit="onSubmit"
    @reset="onReset"
  >
    <h4 class="form-title">
      Add new certificate and n6login:
    </h4>
    <p>
      Just a placeholder
    </p>
  </b-form>
</template>
