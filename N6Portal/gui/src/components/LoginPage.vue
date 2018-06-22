<script>
import qs from 'qs';
import CONFIG from '@/config/config.json';

const baseURL = CONFIG.baseURL;

export default {
  data() {
    return {
      userId: undefined,
      orgId: undefined,
      password: undefined,
      flashStore: this.flash(),
    };
  },

  methods: {
    login() {
      this.axios
        .create({
          withCredentials: true,
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        })
        // parameters send with POST request are being
        // converted by the `qs` library first, so they
        // are properly parsed on a server side
        .post(baseURL.concat('/login'), qs.stringify(
          {'user_id': this.userId,
            'org_id': this.orgId,
            'password': this.password}))
        .then(response => {
          this.login_success();
        })
        .catch(error => {
          this.login_error(error, 'Invalid credentials.');
        });
    },
    cert_login() {
      this.axios
        .create({
          withCredentials: true,
        })
        .get(baseURL.concat('/cert_login'))
        .then(response => {
          this.login_success();
        })
        .catch(error => {
          this.login_error(error, 'Invalid or no certificate.');
        });
    },
    login_success() {
      this.flashStore.destroyAll();
      this.flash('You have been logged in.', 'success');
      this.$router.push('/');
    },
    login_error(error, msg) {
      console.error(error);
      if (error.response.status && error.response.status === 403) {
        this.flashStore.destroyAll();
        this.flash(msg, 'error');
      } else {
        this.$router.push('/error');
      }
    },
  },
};
</script>


<template>
  <b-container>
    <div class="b-row">
      <div class="span12">
        <button
          v-if="$store.state.certificateFetched"
          class="btn btn-success"
          @click="cert_login"
        >
          Sign in with certificate
        </button>
        <form
          class="form-horizontal"
          @submit.prevent="login"
        >
          <fieldset>
            <div id="legend">
              <legend class="">
                Login
              </legend>
            </div>
            <div class="control-group">
              <!-- Username -->
              <label
                class="control-label"
                for="userId"
              >
                Username
              </label>
              <div class="controls">
                <input
                  v-model="userId"
                  id="userId"
                  type="text"
                  name="userId"
                  placeholder=""
                  class="input-xlarge"
                />
              </div>
            </div>
            <div class="control-group">
              <!-- Organization -->
              <label
                class="control-label"
                for="orgId"
              >
                Organization
              </label>
              <div class="controls">
                <input
                  v-model="orgId"
                  id="orgId"
                  type="text"
                  name="orgId"
                  placeholder=""
                  class="input-xlarge"
                />
              </div>
            </div>
            <div class="control-group">
              <!-- Password-->
              <label
                class="control-label"
                for="password"
              >
                Password
              </label>
              <div class="controls">
                <input
                  v-model="password"
                  id="password"
                  type="password"
                  name="password"
                  placeholder=""
                  class="input-xlarge"
                />
              </div>
            </div>
            <div class="control-group">
              <!-- Button -->
              <div class="controls">
                <button
                  class="btn btn-success"
                  type="submit"
                >
                  Sign in
                </button>
              </div>
            </div>
            <p>
              forgot your password?
              <a href="#">click here</a>
            </p>
          </fieldset>
        </form>
      </div>
    </div>
  </b-container>
</template>


<style scoped>
button {
  margin: 20px;
}
</style>
