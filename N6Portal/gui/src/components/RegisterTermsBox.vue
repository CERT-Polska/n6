<template>
  <div class="TermsBox">
    <div class="TermsBox-Content">
      <h1>{{ currentLang.pageTitle }}</h1>
      <lang-controls />
      <p class="TermsBox-precaution">{{ currentLang.precaution }}</p>
      <h2>{{ currentLang.title }}</h2>
      <ol class="TermsList">
        <li v-for="term in currentLang.terms">{{ term }}</li>
      </ol>
    </div>
    <div class="TermsBox-InputGroup">
      <label for="terms-checkbox">{{ currentLang.checkboxLabel }}</label>
      <input type="checkbox"
             v-model="termsCheckbox"
             name="terms-checkbox"
             id="terms-checkbox" />
    </div>
    <div class="TermsBox-Buttons">
      <base-button @click="okRegister">{{ currentLang.okLabel }}</base-button>
      <base-button @click="cancelRegister">{{ currentLang.cancelLabel }}</base-button>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex';
import localeEN from '../locales/EN/register_terms.json';
import localePL from '../locales/PL/register_terms.json';

import BaseButton from './BaseButton';
import LangControls from './LangControls';

export default {
  data() {
    return {
      termsCheckbox: false,
      textsEN: localeEN,
      textsPL: localePL,
    }
  },
  components: {
    LangControls,
    BaseButton,
  },
  computed: {
    ...mapGetters('lang', [
      'currentLangKey',
    ]),
    currentLang() {
      return this[this.currentLangKey];
    },
  },
  methods: {
    okRegister() {
      if (this.termsCheckbox) {
        this.$emit('okClicked');
      } else {
        this.$notify({
          group: 'flash',
          type: 'warn',
          text: this.currentLang.errorFlashMsg,
        });
      }
    },
    cancelRegister() {
      this.$router.push({name: 'main'});
    },
  },
}
</script>

<style scoped lang="scss">
@import '~@styles/_values.scss';

.TermsBox {
  max-width: 50%;
  margin: $margin-medium auto;
}

/deep/ .TermsList {

  li {
    list-style-type: decimal;
    margin-bottom: $margin-extra-small;
    text-align: justify;
  }
}

.TermsBox-precaution {
  color: $color-red-dark;
  line-height: 1.4em;
}

.TermsBox-Content {

  text-align: justify;
  margin-bottom: $margin-extra-extra-large;

  h1 {
    font-size: $font-size-large;
    font-weight: bolder;
  }

  h2 {
    font-size: $font-size-medium;
    font-weight: bolder;
  }

  > * {
    margin-bottom: $margin-extra-large;
  }
}

.TermsBox-Buttons {
  text-align: center;
}

.TermsBox-InputGroup {
  margin-top: $margin-small;
  margin-bottom: $margin-extra-small;
  font-weight: bolder;
}
</style>
