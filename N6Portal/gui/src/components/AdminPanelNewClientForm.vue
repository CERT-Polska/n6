<script>
export default {
  data() {
    return {
      originalForm: {},
      form: {
        email: [],
        asn: [],
        cc: [],
        ip: [],
        fqdn: [],
        url: [],
        emailNotificationTime: [],
        fullAccess: false,
        streamApi: true,
        emailNotify: false,
        timeZone: true,
        access_inside: true,
        access_search: false,
        english: false,
        refint: 'cn=clients,ou=org-groups,dc=n6,dc=cert,dc=pl',
        name: '',
      },
      commandURL: 'insert-new-org',
      emails: 1,
      asns: 1,
      countries: 1,
      ips: 1,
      fqdns: 1,
      urls: 1,
      emailNotificationTimes: 1,
    };
  },

  mounted() {
    this.originalForm = JSON.parse(JSON.stringify(this.form));
  },

  methods: {
    onSubmit(evt) {
      evt.preventDefault();
      this.$emit('formSubmit', this.form, this.commandURL);
    },
    onReset(evt) {
      evt.preventDefault();
      this.form = JSON.parse(JSON.stringify(this.originalForm));
      this.emails = 1;
      this.asns = 1;
      this.countries = 1;
      this.ips = 1;
      this.fqdns = 1;
      this.urls = 1;
      this.emailNotificationTimes = 1;
    },
  },
};
</script>


<template>
  <b-form
    @submit="onSubmit"
    @reset="onReset"
  >
    <h4 class="form-title">Add new organization:</h4>
    <b-form-group
      :label-cols="2"
      label="name:"
      horizontal
      breakpoint="md"
    >
      <b-form-input
        v-model="form.name"
        type="text"
        required
        size="sm"
      >
        Name
      </b-form-input>
    </b-form-group>

    <b-form-group
      :label-cols="2"
      label="refint:"
      horizontal
      breakpoint="md"
    >
      <b-form-input
        v-model="form.refint"
        type="text"
        required
        size="sm"
      />
    </b-form-group>

    <b-form-group
      :label-cols="2"
      label="e-mail:"
      horizontal
      breakpoint="md"
    >
      <b-input-group
        v-for="n of emails"
        :key="n"
      >
        <b-form-input
          v-model="form.email[n-1]"
          type="email"
          size="sm"
        />
        <b-input-group-append v-if="n==emails">
          <b-btn
            v-if="n>1"
            class="addon-button addon-minus"
            variant="outline-danger"
            size="sm"
            @click="emails--"
          >-</b-btn>
          <b-btn
            v-if="n<=10"
            class="addon-button addon-plus"
            variant="outline-success"
            size="sm"
            @click="emails++"
          >+</b-btn>
        </b-input-group-append>
      </b-input-group>
    </b-form-group>

    <b-form-group
      :label-cols="2"
      label="asn:"
      horizontal
      breakpoint="md"
    >
      <b-input-group
        v-for="n of asns"
        :key="n"
      >
        <b-form-input
          v-model="form.asn[n-1]"
          type="text"
          size="sm"
        />
        <b-input-group-append v-if="n==asns">
          <b-btn
            v-if="n>1"
            class="addon-button addon-minus"
            variant="outline-danger"
            size="sm"
            @click="asns--"
          >-</b-btn>
          <b-btn
            v-if="n<=10"
            class="addon-button addon-plus"
            variant="outline-success"
            size="sm"
            @click="asns++"
          >+</b-btn>
        </b-input-group-append>
      </b-input-group>
    </b-form-group>

    <b-form-group
      horizontal
      label="country:"
      :label-cols="2" breakpoint="md"
    >
      <b-input-group
        v-for="n of countries"
        :key="n">
        <b-form-input
          v-model="form.cc[n-1]"
          type="text"
          size="sm"
        />
        <b-input-group-append v-if="n==countries">
          <b-btn
            v-if="n>1"
            class="addon-button addon-minus"
            variant="outline-danger"
            size="sm"
            @click="countries--"
          >-</b-btn>
          <b-btn
            v-if="n<=10"
            class="addon-button addon-plus"
            variant="outline-success"
            size="sm"
            @click="countries++"
          >+</b-btn>
        </b-input-group-append>
      </b-input-group>
    </b-form-group>

    <b-form-group
      horizontal
      label="IP:"
      :label-cols="2"
      breakpoint="md"
    >
      <b-input-group
        v-for="n of ips"
        :key="n"
      >
        <b-form-input
          v-model="form.ip[n-1]"
          type="text"
          size="sm"
        />
        <b-input-group-append v-if="n==ips">
          <b-btn
            v-if="n>1"
            class="addon-button addon-minus"
            variant="outline-danger"
            size="sm"
            @click="ips--"
          >-</b-btn>
          <b-btn
            v-if="n<=10"
            class="addon-button addon-plus"
            variant="outline-success"
            size="sm"
            @click="ips++"
          >+</b-btn>
        </b-input-group-append>
      </b-input-group>
    </b-form-group>

    <b-form-group
      horizontal
      label="fqdn:"
      :label-cols="2"
      breakpoint="md"
    >
      <b-input-group
        v-for="n of fqdns"
        :key="n"
      >
        <b-form-input
          v-model="form.fqdn[n-1]"
          type="text"
          size="sm"
        />
        <b-input-group-append v-if="n==fqdns">
          <b-btn
            v-if="n>1"
            class="addon-button addon-minus"
            variant="outline-danger"
            size="sm"
            @click="fqdns--"
          >-</b-btn>
          <b-btn
            v-if="n<=10"
            class="addon-button addon-plus"
            variant="outline-success"
            size="sm"
            @click="fqdns++"
          >+</b-btn>
        </b-input-group-append>
      </b-input-group>
    </b-form-group>

    <b-form-group
      horizontal
      label="URL:"
      :label-cols="2"
      breakpoint="md"
    >
      <b-input-group
        v-for="n of urls"
        :key="n"
      >
        <b-form-input
          v-model="form.url[n-1]"
          type="url"
          size="sm"
        />
        <b-input-group-append v-if="n==urls">
          <b-btn
            v-if="n>1"
            class="addon-button addon-minus"
            variant="outline-danger"
            size="sm"
            @click="urls--"
          >-</b-btn>
          <b-btn
            @click="urls++"
            v-if="n<=10"
            variant="outline-success"
            class="addon-button addon-plus"
            size="sm"
          >+</b-btn>
        </b-input-group-append>
      </b-input-group>
    </b-form-group>

    <b-form-checkbox v-model="form.emailNotify">e-mail notifications</b-form-checkbox>

    <b-form-group
      v-if="form.emailNotify"
      label="notification time:"
      label-cols="3"
      horizontal
      breakpoint="md"
    >
      <b-input-group
        v-for="n of emailNotificationTimes"
        :key="n"
      >
        <b-form-input
          v-model="form.emailNotificationTime[n-1]"
          type="time"
          size="sm"
        />
        <b-input-group-append v-if="n==emailNotificationTimes">
          <b-btn
            v-if="n>1"
            class="addon-button addon-minus"
            variant="outline-danger"
            size="sm"
            @click="emailNotificationTimes--"
          >-</b-btn>
          <b-btn
            v-if="n<=10"
            class="addon-button addon-plus"
            variant="outline-success"
            size="sm"
            @click="emailNotificationTimes++"
          >+</b-btn>
        </b-input-group-append>
      </b-input-group>
    </b-form-group>

    <b-form-checkbox v-model="form.timeZone">
      local time zone
    </b-form-checkbox>
    <b-form-checkbox v-model="form.streamApi">
      n6 stream API enabled
    </b-form-checkbox>
    <b-form-checkbox v-model="form.access_inside">
      access to threats inside organization
    </b-form-checkbox>
    <b-form-checkbox v-model="form.access_search">
      access to search events
    </b-form-checkbox>
    <b-form-checkbox v-model="form.fullAccess">
      full access to n6 REST API
    </b-form-checkbox>
    <b-form-checkbox v-model="form.english">
      English language version
    </b-form-checkbox>

    <b-button
      type="submit"
      class="form-btn"
      variant="success"
    >
      Submit
    </b-button>
    <b-button
      type="reset"
      class="form-btn"
      variant="danger"
    >
      Clear
    </b-button>
  </b-form>
</template>


<style scoped>
.col-form-legend,
input[type="text"],
input[type="email"],
input {
  font-size: 0.9em;
}
</style>
