<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/check-circle';
import 'vue-awesome/icons/info-circle';

import { DEFAULT_EN_LANG_TAG } from '@/helpers/lang';
import localeRegisterEN from '../locales/EN/register_form.json';
import localeRegisterPL from '../locales/PL/register_form.json';
import localeSettingsChangeEN from '../locales/EN/settings_form';

export default {
  components: {
    Icon,
  },

  props: {
    status: {
      type: String,
    },
    langTag: {
      type: String,
      default: DEFAULT_EN_LANG_TAG,
    },
  },

  data() {
    return {
      infoMessages: {
        'register_success': {
          en: localeRegisterEN,
          pl: localeRegisterPL,
          status: 'success',
        },
        'settings_change_pending': {
          en: localeSettingsChangeEN,
          status: 'success',
        },
      },
    };
  },

  computed: {
    currentInfoData() {
      if (this.status === undefined ||
        !this.infoMessages.hasOwnProperty(this.status)) {
        return {
          heading: '',
          message: '',
          status: 'info',
        }
      }
      return this.infoMessages[this.status];
    },
    heading() {
      return this.currentInfoData[this.langTag].success_page_heading;
    },
    message() {
      return this.currentInfoData[this.langTag].success_page_message;
    },
  },

};
</script>

<template>
  <div>
    <icon
      v-if="currentInfoData.status === 'success'"
      name="check-circle"
      scale="3.8"
      class="Success-Icon"
    />
    <icon
      v-else-if="currentInfoData.status === 'info'"
      name="info-circle"
      scale="3.8"
      class="Info-Icon"
    />
    <h1>
      {{ heading }}
    </h1>
    <p>
      {{ message }}
    </p>
  </div>
</template>


<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

div {
  text-align: center;
}

h1 {
  margin-bottom: $margin-large;
  font-size: $font-size-large;
  font-weight: 700;
}

.Success-Icon, .Info-Icon {
  margin-bottom: $margin-large;
}

.Success-Icon {
  color: $color-green-dark;
}

.Info-Icon {
  color: $color-blue-light;
}
</style>
