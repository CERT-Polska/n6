<template>
  <div class="InputGroup">
    <input-label :id-val="idVal" :label-val="labelVal" :tooltip-text="tooltipText" />
    <base-input :class="{ InputHasError: isTouched && errMsgs,
                          InactiveInput: disabled }"
                :type="inputType"
                v-model="inputValue"
                :name="idVal"
                :id="idVal"
                @blur="blurHandler"
                :readonly="disabled"
    />
    <div class="ErrorMsgWrapper">
      <div class="error-msgs" v-if="isTouched && errMsgs">
        <p v-for="msg in errMsgs">{{ msg }}</p>
      </div>
    </div>
  </div>
</template>

<script>
import BaseInput from './BaseInput';
import InputLabel from './InputLabel';
import LangSetMixin from '../mixins/LangSetMixin';
import validationErrorMessagesMixin from '../mixins/ValidationErrorMessages';

export default {
  data() {
    return {
      idVal: this.criterion.id,
      inputType: this.criterion.type,
    }
  },
  components: {
    BaseInput,
    InputLabel,
  },
  mixins: [LangSetMixin, validationErrorMessagesMixin],
  props: {
    criterion: {
      type: Object,
      required: true,
    },
    disabled: {
      type: Boolean,
      required: false,
    },
    v: Object,
    value: String,
  },
  computed: {
    langKey() {
      return 'texts' + this.validatedStoredLang.toUpperCase();
    },
    labelVal() {
      return this.criterion[this.langKey].label;
    },
    tooltipText() {
      return this.criterion[this.langKey].help;
    },
    inputValue: {
      get() {
        return this.value;
      },
      set(value) {
        this.$emit('input', value);
      },
    },
    hasErrors() {
      return this.v.$anyError;
    },
    isTouched() {
      return this.v.$dirty;
    },
    errMsgs() {
      return this.validationErrorMessages(this.v, this.validatedStoredLang);
    },
  },
  methods: {
    blurHandler() {
      this.v.$touch();
    },
    changeHandler(e) {
      this.$emit('change', e);
    },
  },
}
</script>

<style scoped lang="scss">
  @import '~@styles/_animations.scss';
  @import '~@styles/_values.scss';
  @import '~@styles/base.scss';

  .InputHasError {
    border: 1px $color-red-dark dotted !important;
  }

  .InactiveInput {
    @include InactiveInputGradient;
    pointer-events: none;
    border: none !important;
  }
</style>
