<script>
import LangSetMixin from '../mixins/LangSetMixin';

export default {

  mixins: [LangSetMixin],

  methods: {
    setNewLang(tag) {
      this.storeLang(tag, true);
    },
  },
};
</script>

<template>
  <div class="LangBox">
    <a @click.prevent="setNewLang('en')">
      <img src="~@/images/lang_en.png" alt="Set language to English" />
    </a>
    <a @click.prevent="setNewLang('pl')">
      <img src="~@/images/lang_pl.png" alt="Set language to Polish" />
    </a>
  </div>
</template>


<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

.LangBox {
  a {
    margin-right: $margin-extra-extra-small;
  }
}
</style>
