import { mapState } from 'vuex';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/undo';

// the mixin is supposed to be used within the EditConfigForm
// component's field components, as it extends their properties
// and methods, so they can access proper VueX's 'form' store's
// state objects and recognize, whether the input value has been
// edited

export default {
  components: {
    Icon,
  },
  computed: {
    ...mapState('form', [
      'formDisabled',
      'originalFields',
      'updatedFields',
    ]),
    isEdited() {
      return this.updatedFields.hasOwnProperty(this.idVal);
    },
    langKey() {
      return 'textsEN';
    },
  },
  methods: {
    undoHandler(e) {
      if (!this.disabled) {
        this.$emit('valueChange', {
          criterionType: 'string',
          id: this.idVal,
          type: 'undo',
          value: null,
        });
      }
    },
  },
};
