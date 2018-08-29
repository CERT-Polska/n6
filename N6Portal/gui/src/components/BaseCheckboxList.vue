<!-- List of checkboxes with labels -->


<script>
import BaseFormControl from './BaseFormControl';

export default {
  components: {
    BaseFormControl,
  },

  props: {
    // List of all the checkboxes. Each checkbox is an object of format
    // { label, id, checked }.
    checkboxes: {
      type: Array,
      required: true,
      validator: checkboxes => {
        let requiredProperties = ['label', 'id', 'checked'];
        return checkboxes.every(checkbox =>
          requiredProperties.every(checkbox.hasOwnProperty, checkbox)
        );
      },
    },
    // Prefix added to all checkboxes ID-s
    idPrefix: {
      type: String,
      required: false,
    },
  },

  methods: {
    controlId(id) {
      let prefix = this.idPrefix ? `${this.idPrefix}-` : '';
      return prefix + id;
    },
  },
};
</script>


<template>
  <ul class="CheckboxList">
    <li
      v-for="checkbox in checkboxes"
      :key="checkbox.id"
      class="CheckboxList-Item"
    >
      <base-form-control
        :id="controlId(checkbox.id)"
        size="fit"
        checkbox
      >
        <input
          slot="input"
          v-model="checkbox.checked"
          type="checkbox"
          :checked="checkbox.checked"
        />
        <label slot="label">
          {{ checkbox.label }}
        </label>
      </base-form-control>
    </li>
  </ul>
</template>


<style
  lang="scss"
  scoped
>
@import '~@styles/_values.scss';

.CheckboxList {
  padding: $padding-extra-small;
}

.CheckboxList-Item {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;

  & + & {
    margin-top: $margin-extra-small;
  }
}
</style>
