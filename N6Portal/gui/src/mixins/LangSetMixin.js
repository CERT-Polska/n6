import { mapState, mapGetters } from 'vuex';

export default {

  computed: {
    ...mapState('lang', [
      'storedLang',
    ]),
    ...mapGetters('lang', [
      'validatedStoredLang',
    ]),
  },

  methods: {
    initializeLang() {
      this.$store.dispatch('lang/initializeStore');
    },
    storeLang(tag, validated = false) {
      this.$store.dispatch('lang/storeLang', tag, validated);
    },
  },

};
