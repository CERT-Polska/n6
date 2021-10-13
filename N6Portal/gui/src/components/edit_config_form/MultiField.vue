<template>
  <div class="InputGroup">
    <base-input :class="{ InputHasError: isTouched && errMsgs,
                          EditedInput: isEdited && !hasErrors }"
                :type="inputType"
                v-model="inputValue"
                :name="idVal"
                :id="idVal"
                :readonly="formDisabled"
                @change="changeHandler"
                @blur="blurHandler" />
    <div class="ErrorMsgWrapper">
      <div class="error-msgs" v-if="isTouched && errMsgs">
        <p v-for="msg in errMsgs">{{ msg }}</p>
      </div>
    </div>
  </div>
</template>

<script>
import MultiCriterion from '../MultiCriterion';
import EditSettingsFormMixin from '@/mixins/EditSettingsFormMixin';

export default {
  extends: MultiCriterion,
  mixins: [EditSettingsFormMixin],
  computed: {
    isEdited() {
      return this.updatedFields[this.idVal] &&
        !this.originalFields[this.idVal].includes(this.value) &&
        this.value;
    },
  },
  methods: {
    changeHandler(e) {
      this.$emit('change', {
        criterionType: 'array',
        type: 'change',
        index: this.index,
        id: this.idVal,
        value: e,
      });
    },
    undoHandler(e) {
      this.$emit('change', {
        criterionType: 'array',
        id: this.idVal,
        type: 'undo',
        value: null,
      });
    },
  },
}
</script>
