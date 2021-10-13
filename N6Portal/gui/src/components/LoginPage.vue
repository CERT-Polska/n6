<script>
// Commented out as a part of disabling username and password login
// import qs from 'qs';
import axios from 'axios';
import { mapGetters } from 'vuex';
import Spinner from 'vue-spinner-component/src/Spinner';
import BaseButton from './BaseButton';
import BaseForm from './BaseForm';
import BaseFormControl from './BaseFormControl';
import BaseFormActions from './BaseFormActions';
import BaseFormMessage from './BaseFormMessage';
import BaseInput from './BaseInput';
import BaseLink from './BaseLink';
import CONFIG from '@/config/config.json';
import {FLASH_MESSAGE_LABELS} from '@/helpers/constants';

// Commented out as a part of disabling username and password login
// const INVALID_CREDENTIALS_MESSAGE = 'You provided invalid login information. Try again.';
const INVALID_CERTIFICATE_MESSAGE = 'You provided invalid or no certificate';
const SERVER_DOWN_MESSAGE = 'There seems to be a problem with our server. Please try again soon.';
const NO_CERTIFICATE_MESSAGE = 'Certificate not found. Add it in the browser to log in';

const FORBIDDEN_REQUEST_CODE = 403;
const INTERNAL_SERVER_ERROR_REQUEST_CODE = 500;

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
    Spinner,
  },

  data() {
    return {
      // Empty strings needed (instead of undefined) for browser validation
      // on required attributes to work properly
      userId: '',
      orgId: '',
      password: '',
      errorMessage: undefined,
      loginPending: false,
    };
  },

  beforeRouteEnter (to, from, next) {
    next(vm => {
      if (vm.isCertificateFetched) {
        vm.$notify({
          group: 'flash',
          type: 'info',
          data: {
            label: FLASH_MESSAGE_LABELS.cert_avail_label,
          },
          text: 'You are ready to sign in with certificate',
          duration: -1,
        });
      }
    });
  },

  beforeRouteLeave (to, from, next) {
    this.destroyMsgByLabel(FLASH_MESSAGE_LABELS.cert_avail_label, 'main_notifications');
    next();
  },

  inject: ['destroyMsgByLabel'],

  computed: {
    ...mapGetters('session', [
      'isInsideAvailable',
      'isSearchAvailable',
    ]),
    isCertificateFetched() {
      const result = this.$store.state.session.isCertificateFetched;
      // The line setting error message should be removed, as soon as logging in
      // with username and password is enabled (uncommented) again, as it
      // assumes that logging in with certificate is the only way to log in.
      this.errorMessage = result ? undefined : NO_CERTIFICATE_MESSAGE;
      return result;
    },
  },

  methods: {
    sign_up() {
      this.$router.push({name: 'register'});
    },
    login() {
      // Commented as a part of temporarily disabling logging in with username
      // and password
      //
      // this.loginPending = true;
      // axios
      //   .create({
      //     withCredentials: true,
      //     headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      //   })
      //   // parameters send with POST request are being
      //   // converted by the `qs` library first, so they
      //   // are properly parsed on a server side
      //   .post(baseURL.concat('/login'), qs.stringify({
      //     'user_id': this.userId,
      //     'org_id': this.orgId,
      //     'password': this.password,
      //   }))
      //   .then(response => {
      //     this.login_success();
      //   })
      //   .catch(error => {
      //     this.login_error(error, {
      //       [FORBIDDEN_REQUEST_CODE]: INVALID_CREDENTIALS_MESSAGE,
      //       [INTERNAL_SERVER_ERROR_REQUEST_CODE]: SERVER_DOWN_MESSAGE,
      //     });
      //   });
    },

    cert_login() {
      this.loginPending = true;
      axios
        .create({
          withCredentials: true,
        })
        .get(baseURL.concat('/cert_login'))
        .then(response => {
          this.login_success();
        })
        .catch(error => {
          this.login_error(error, {
            [FORBIDDEN_REQUEST_CODE]: INVALID_CERTIFICATE_MESSAGE,
            [INTERNAL_SERVER_ERROR_REQUEST_CODE]: SERVER_DOWN_MESSAGE,
          });
        });
    },

    login_success() {
      // In case there is a remaining 'dashboardPayload' localStorage
      // key (hasn't been deleted on log out), delete it now, to avoid
      // the error, where cached dashboard data related to some
      // organization will be used as other organization's data.
      this.$store.dispatch('dashboard/uncachePayload');
      this.errorMessage = undefined;
      this.$notify({
        group: 'flash',
        type: 'success',
        text: 'You have been logged in',
      });
      // Use the VueX session state to determine the next route after
      // the successful login:
      // * If the user has access to the 'Inside' resource, but not
      //   'Search' - go to the 'dashboard' view.
      // * If he has access to both 'Inside' and 'Search' - go to
      //   the 'search' view.
      // * If he does not have access to the 'Inside' - go to
      //   the 'search' view.
      //
      // This conditions are being resolved here, because it is
      // possible to easily fetch the session info. It would have
      // been better to resolve it in a function assigned to the
      // route's 'redirect' property in the Router, but there is no
      // access to the session info there. Also the proper place would
      // have been the Router's 'beforeEach' navigation guard, but
      // adding the condition causes the infinite loop.
      this.$store.dispatch('session/loadSessionInfo').then(() => {
        if (this.isInsideAvailable && !this.isSearchAvailable) {
          this.$router.push({name: 'dashboard'});
        } else {
          this.$router.push({name: 'search'});
        }
      }).catch(() => {
        this.$router.push({name: 'main'});
      });
    },

    // messages is a map of HTTP request status codes to error messages
    login_error(error, messages) {
      this.loginPending = false;
      if (error.response && error.response.status && (error.response.status in messages)) {
        console.info(`Unsuccessful login attempt: ${error}`);
        this.errorMessage = messages[error.response.status];
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

    <!-- Login with username and password -->
    <!-- Currently disabled. Will be enabled at some point and that's why it's
      -- commented and not removed -->
    <!-- <!&#45;&#45; Username &#45;&#45;> -->
    <!-- <base&#45;form&#45;control id="username"> -->
    <!--   <template slot="label"> -->
    <!--     Username: -->
    <!--   </template> -->
    <!--   <base&#45;input -->
    <!--     slot="input" -->
    <!--     v&#45;model="userId" -->
    <!--     maxlength="50" -->
    <!--     required -->
    <!--     type="text" -->
    <!--   /> -->
    <!-- </base&#45;form&#45;control> -->
    <!--  -->
    <!-- <!&#45;&#45; Organization &#45;&#45;> -->
    <!-- <base&#45;form&#45;control id="organization"> -->
    <!--   <template slot="label"> -->
    <!--     Organization: -->
    <!--   </template> -->
    <!--   <base&#45;input -->
    <!--     slot="input" -->
    <!--     v&#45;model="orgId" -->
    <!--     maxlength="60" -->
    <!--     required -->
    <!--     type="text" -->
    <!--   /> -->
    <!-- </base&#45;form&#45;control> -->
    <!--  -->
    <!-- <!&#45;&#45; Password&#45;&#45;> -->
    <!-- <base&#45;form&#45;control id="password"> -->
    <!--   <template slot="label"> -->
    <!--     Password: -->
    <!--   </template> -->
    <!--   <base&#45;input -->
    <!--     slot="input" -->
    <!--     v&#45;model="password" -->
    <!--     maxlength="50" -->
    <!--     required -->
    <!--     type="password" -->
    <!--   /> -->
    <!-- </base&#45;form&#45;control> -->
    <!--  -->
    <!-- <base&#45;form&#45;actions> -->
    <!--   <!&#45;&#45; Submit &#45;&#45;> -->
    <!--   <base&#45;button -->
    <!--     type="submit" -->
    <!--     role="primary" -->
    <!--     :disabled="loginPending" -->
    <!--   > -->
    <!--     Sign in -->
    <!--   </base&#45;button> -->
    <!-- </base&#45;form&#45;actions> -->

    <!-- Login with certificate -->
    <base-form-actions
      :disabled="loginPending"
    >
      <!-- Signing with certificate -->
      <base-button
        v-if="isCertificateFetched"
        @click.native="cert_login"
        type="button"
        role="primary"
      >
        Sign in with certificate
      </base-button>
      <base-button
        v-else
        @click.native="sign_up"
        type="button"
        role="primary"
      >
        Sign up your organization
      </base-button>
    </base-form-actions>

    <!-- Forgot password -->
    <!-- For now disabled the same ass username and password inputs -->
    <!-- <base&#45;form&#45;message> -->
    <!--   Forgot your password? -->
    <!--   <!&#45;&#45; TODO: This link should go somewhere. &#45;&#45;> -->
    <!--   <base&#45;link -->
    <!--     href="#" -->
    <!--   > -->
    <!--     Click here -->
    <!--   </base&#45;link> -->
    <!-- </base&#45;form&#45;message> -->
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
