<template>
  <a @click.prevent="onClick" class="ActionButton">
    <icon
      name="trash"
      scale="0.8"
    />
  </a>
</template>

<script>
import 'vue-awesome/icons/trash';
import { mapState } from 'vuex';

import InputActionButton from '../InputActionButton';

export default {
  extends: InputActionButton,
  props: {
    inputObj: {
      type: Array,
      required: true,
    },
    fieldName: {
      type: String,
      required: true,
    },
    index: {
      type: Number,
      required: true,
    },
  },
  inject: ['areArraysEqual'],
  computed: {
    ...mapState('form', [
      'originalFields',
      'updatedFields',
    ]),
  },
  methods: {
    _manageState() {
      if (this.areArraysEqual(this.inputObj, this.originalFields[this.fieldName])) {
        this.$store.commit('form/deleteUpdatedField', this.fieldName);
      } else {
        this.$store.commit('form/addUpdatedField', {
          fieldName: this.fieldName,
          value: this.inputObj.slice(),
        });
      }
    },
    onClick(e) {
      if (!this.checkIfFormDisabled()) {
        if (this.inputObj.length) {
          this.inputObj.splice(this.index, 1);
          this._manageState();
        }
      }
    },
  },
};
</script>

<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

.ActionButton {
  color: $color-red-dark;

  &:hover {
    color: $color-yellow-dark;
  }
}
</style>
