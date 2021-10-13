<script>
import Icon from 'vue-awesome/components/Icon';
import INTERNAL_CONFIG from '@/config/config.json';
// TODO: change path to '@/config/internalConfig.json' after parametrization
import { mapGetters, mapState } from 'vuex';

import BaseButton from './BaseButton';
import errorMessagesEN from '../locales/EN/error_messages.json';
import errorMessagesPL from '../locales/PL/error_messages.json';
import settingsFormEN from '../locales/EN/settings_form.json';
import settingsFormPL from '../locales/PL/settings_form.json';

const { multivaluedInputLimit } = INTERNAL_CONFIG;

export default {
  data() {
    return {
      multivaluedInputLimit: multivaluedInputLimit,
      textsEN: {
        errorMessages: errorMessagesEN,
        settingsForm: settingsFormEN,
      },
      textsPL: {
        errorMessages: errorMessagesPL,
        settingsForm: settingsFormPL,
      },
    }
  },
  components: {
    Icon,
  },
  extends: BaseButton,
  props: ['inputObj'],
  computed: {
    ...mapGetters('lang', [
      'currentLangKey',
    ]),
    ...mapState('form', [
      'formDisabled',
    ]),
    currentLangObj() {
      return this[this.currentLangKey];
    },
  },
  methods: {
    checkIfFormDisabled() {
      if (this.formDisabled) {
        this.$notify({
          group: 'flash',
          type: 'error',
          // use the English locale until a language switching feature
          // has been implemented everywhere (the message below applies
          // only to the settings change form)
          text: this.textsEN.settingsForm.form_disabled_message,
        });
        return true;
      }
      return false;
    },
  },
};
</script>
