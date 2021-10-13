<script>
import RegisterForm from './RegisterForm';
import RegisterTermsBox from './RegisterTermsBox';

export default {
  data() {
    return {
      termsAgreed: false,
    }
  },
  components: {
    RegisterForm,
    RegisterTermsBox,
  },
};
</script>


<template>
  <register-terms-box @okClicked="termsAgreed=true" v-if="!termsAgreed" />
  <register-form v-else :terms-agreed="termsAgreed" />
</template>
