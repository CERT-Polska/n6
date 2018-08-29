<!-- Dropdown menu activated by button
-->


<script>
import capitalize from 'lodash-es/capitalize';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/chevron-down';

const EVENT_PROPERTY_ID_NAME = '_dropdownId';

export default {
  components: {
    Icon,
  },

  props: {
    icon: {
      type: Boolean,
      default: true,
    },
    // How align dropdown content in relation to the button
    align: {
      type: String,
      default: 'left',
      validator: value => ['left', 'right', 'stretch'].includes(value),
    },
  },

  data() {
    return {
      dropdownOpened: false,
      // Unique ID identifying the dropdown. Used to trackign which dropdowns
      // to close.
      id: Math.random(),
    };
  },

  methods: {
    toggleDropdown(event) {
      if (this.dropdownOpened) {
        this.closeDropdown(event);
        document.removeEventListener('click', this.closeDropdown);
      } else {
        this.openDropdown();
        document.addEventListener('click', this.closeDropdown);
      }
      this.addIdToClickEvent(event);
    },

    openDropdown() {
      this.dropdownOpened = true;
    },

    closeDropdown(event) {
      if (
        !event ||
        ![EVENT_PROPERTY_ID_NAME] ||
        event[EVENT_PROPERTY_ID_NAME] !== this.id
      ) {
        this.dropdownOpened = false;
      }
    },

    addIdToClickEvent(event) {
      // Cancel the original event
      event.stopPropagation();
      // Create a new event with id property and emit it
      if (event.currentTarget.parentElement) {
        let newEvent = new MouseEvent('click', {
          bubbles: true,
        });
        newEvent[EVENT_PROPERTY_ID_NAME] = this.id;
        // Emitted on parent to not trigger the same handler again
        event.currentTarget.parentElement.dispatchEvent(newEvent);
      }
    },

    openedCssStateClass() {
      return (this.dropdownOpened) ? 'Dropdown--IsOpened' : '';
    },

    iconCssClassSuffix() {
      return this.icon ? '--WithIcon' : '--NoIcon';
    },

    alignCssClassSuffix() {
      return `--Aligned${capitalize(this.align)}`;
    },

    dropdownContentCssClass() {
      return `Dropdown-Content${this.alignCssClassSuffix()} ${this.openedCssStateClass()}`;
    },
  },
};
</script>


<template>
  <div class="Dropdown">
    <div
      :class="`Dropdown-Button${iconCssClassSuffix()}`"
      @click="toggleDropdown($event)"
    >
      <slot name="button" />
      <icon
        v-if="icon"
        class="Dropdown-ButtonIcon"
        name="chevron-down"
      />
    </div>
    <div
      class="Dropdown-Content"
      :class="dropdownContentCssClass()"
      @click="addIdToClickEvent($event)"
    >
      <slot name="dropdownContent" />
    </div>
  </div>
</template>


<style
  lang="scss"
  scoped
>
@import '~@styles/_values.scss';

$icon-size: 15px;
$button-padding-right: $padding-small;

.Dropdown {
  display: inline-block;
  // To relatively position the dropdown content
  position: relative;
}

%Dropdown-Button {
  position: relative;
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
}

.Dropdown-Button--WithIcon {
  @extend %Dropdown-Button;
}

.Dropdown-Button--NoIcon {
  @extend %Dropdown-Button;
}

/* Button used inside a slot. No way to target it using a class, so using this
   element selector. */
.Dropdown-Button--WithIcon /deep/ button {
  width: 100%;
  padding-right: $icon-size + $padding-small + $button-padding-right;
}

.Dropdown-ButtonIcon {
  $offset-y: 0;

  position: absolute;
  right: $button-padding-right;
  top: calc(50% - (#{$icon-size} / 2) - #{$offset-y});
  width: $icon-size;
  height: $icon-size;
  cursor: pointer;
}

.Dropdown-Content {
  z-index: $z-index-very-top;
  display: none;
  flex-direction: column;
  flex-wrap: nowrap;
  position: absolute;
  border: $border-width solid $color-grey-light;
  border-radius: $border-radius;
  background-color: $color-background-primary;
  white-space: nowrap;

  &.Dropdown--IsOpened {
    display: flex;
  }
}

.Dropdown-Content--AlignedLeft {
  left: 0;
}

.Dropdown-Content--AlignedRight {
  right: 0;
}

.Dropdown-Content--AlignedStretch {
  width: 100%;
}
</style>
