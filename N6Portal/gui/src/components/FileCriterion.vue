<template>
  <div class="InputGroup">
    <input-label :id-val="idVal" :label-val="labelVal" :tooltip-text="tooltipText" />
      <p v-if="validatedStoredLang === pl_lang_tag" class="Help-Box">Załącz plik żądania
        podpisania certyfikatu (certificate signing request).
        Aby uzyskać dostęp do n6 należy posiadać ważny certyfikat kliencki.
        W celu wygenerowania pliku .csr można użyć narzędzia OpenSSL:</p>
      <p v-else class="Help-Box">Attach a Certificate signing request. Access to the n6 is through
        a valid client certificate.
        To generate .csr you can use OpenSSL:</p>
      <div contenteditable="true" spellcheck="false" class="Help-Copy-Box">
        <p><span class="syntax-cmd">openssl</span> genrsa -out n6.key</p>
        <p>
          <span class="syntax-cmd">openssl</span> req -new -subj <span class="syntax-string">
          "/CN=your.name@organization.com/O=organization.com"</span> -key n6.key -out your.name.csr
        </p>
      </div>
    <input :name="idVal" :id="idVal" :type="inputType" @change="changeHandler" :accept="accept" />
    <div class="ErrorMsgWrapper">
      <div class="error-msgs" v-if="isTouched && errMsgs">
        <p v-for="msg in errMsgs">{{ msg }}</p>
      </div>
    </div>
  </div>
</template>

<script>
import BaseCriterion from './BaseCriterion';
import { DEFAULT_PL_LANG_TAG } from '@/helpers/lang';

export default {
  data() {
    return {
      idVal: this.criterion.id,
      inputType: 'file',
      pl_lang_tag: DEFAULT_PL_LANG_TAG,
    }
  },
  extends: BaseCriterion,
  props: ['criterion', 'v', 'value', 'accept', 'checked', 'index'],
}
</script>

<style lang="scss" scoped>
@import '~@styles/_values.scss';

input {
  margin-top: $margin-small !important;
}

.Help-Box {
  background: $color-grey-extra-extra-light;
  padding: $padding-extra-small;
  font-size: $font-size-extra-small;
}

.Help-Copy-Box {
  display: block;
  width: 98%;
  padding: $padding-extra-small;
  margin: $margin-extra-extra-extra-small auto;
  white-space: nowrap;
  font-size: 14rem;
  line-height: 17rem;
  border: 1px $color-navy-dark solid;

  p::before {
    content: "$ ";
    color: $color-grey-dark;
  }
}

.syntax-cmd {
  color: #995626;
}

.syntax-string {
  color: #4d6442;
}

</style>
