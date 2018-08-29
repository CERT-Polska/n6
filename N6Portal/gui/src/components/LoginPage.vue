<script>
import qs from 'qs';
import axios from 'axios';
import BaseButton from './BaseButton';
import BaseForm from './BaseForm';
import BaseFormControl from './BaseFormControl';
import BaseFormActions from './BaseFormActions';
import BaseFormMessage from './BaseFormMessage';
import BaseInput from './BaseInput';
import BaseLink from './BaseLink';
import CONFIG from '@/config/config.json';

const INVALID_CREDENTIALS_MESSAGE = 'You provided invalid login information. Try again.';
const INVALID_CERTIFICATE_MESSAGE = 'You provided invalid or no certificate';

const baseURL = CONFIG.baseURL;

export default {
  components: {
    BaseButton,
    BaseForm,
    BaseFormActions,
    BaseFormControl,
    BaseFormMessage,
    BaseInput,
    BaseLink,
  },

  data() {
    return {
      // Empty strings needed (instead of undefined) for browser validation
      // on required attributes to work properly
      userId: '',
      orgId: '',
      password: '',
      errorMessage: undefined,
      flashStore: this.flash(),
    };
  },

  computed: {
    isCertificateFetched() {
      return this.$store.state.session.isCertificateFetched;
    },
  },

  methods: {
    login() {
      axios
        .create({
          withCredentials: true,
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        })
        // parameters send with POST request are being
        // converted by the `qs` library first, so they
        // are properly parsed on a server side
        .post(baseURL.concat('/login'), qs.stringify({
          'user_id': this.userId,
          'org_id': this.orgId,
          'password': this.password,
        }))
        .then(response => {
          this.login_success();
        })
        .catch(error => {
          this.login_error(error, INVALID_CREDENTIALS_MESSAGE);
        });
    },

    cert_login() {
      axios
        .create({
          withCredentials: true,
        })
        .get(baseURL.concat('/cert_login'))
        .then(response => {
          this.login_success();
        })
        .catch(error => {
          this.login_error(error, INVALID_CERTIFICATE_MESSAGE);
        });
    },

    login_success() {
      this.errorMessage = undefined;
      this.flashStore.destroyAll();
      this.flash('You have been logged in.', 'success');
      this.$store.dispatch('session/loadSessionInfo')
        .then(() => {
          this.$router.push({name: 'main'});
        });
    },

    login_error(error, msg) {
      if (error.response && error.response.status && error.response.status === 403) {
        console.info(`Unsuccessful login attempt: ${error}`);
        this.errorMessage = msg;
      } else {
        console.error(`Login attempt returned unrecognized response: ${error}`);
        this.$router.push({ name: 'error' });
      }
    },
  },
};
</script>


<template>
  <base-form
    :error-message="errorMessage"
    class="LoginPage"
    @submit.prevent="login"
  >
    <!-- Username -->
    <base-form-control id="username">
      <template slot="label">
        Username:
      </template>
      <base-input
        slot="input"
        v-model="userId"
        maxlength="50"
        required
        type="text"
      />
    </base-form-control>

    <!-- Organization -->
    <base-form-control id="organization">
      <template slot="label">
        Organization:
      </template>
      <base-input
        slot="input"
        v-model="orgId"
        maxlength="60"
        required
        type="text"
      />
    </base-form-control>

    <!-- Password-->
    <base-form-control id="password">
      <template slot="label">
        Password:
      </template>
      <base-input
        slot="input"
        v-model="password"
        maxlength="50"
        required
        type="password"
      />
    </base-form-control>

    <base-form-actions>
      <!-- Submit -->
      <base-button
        type="submit"
        role="primary"
      >
        Sign in
      </base-button>
    </base-form-actions>

    <base-form-actions
      v-if="isCertificateFetched"
    >
      <!-- Signing with certificate -->
      <base-button
        @click.native="cert_login"
        type="button"
        role="primary"
      >
        Sign in with certificate
      </base-button>
    </base-form-actions>

    <!-- Forgot password -->
    <base-form-message>
      Forgot your password?
      <!-- TODO: This link should go somewhere. -->
      <base-link
        href="#"
      >
        Click here
      </base-link>
    </base-form-message>
  </base-form>
</template>


<style
  lang="scss"
  scoped
>
@import '~@styles/_values.scss';

.LoginPage {
  margin-top: $margin-medium;
  margin-left: auto;
  margin-right: auto;
  width: 360px;
}
</style>
