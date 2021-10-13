<template>
  <div class="InputGroup">
    <base-input :class="{ InputHasError: isTouched && errMsgs }"
                :type="inputType"
                v-model="inputValue"
                :name="idVal"
                :id="idVal"
                @blur="blurHandler" />
    <div class="ErrorMsgWrapper">
      <div class="error-msgs" v-if="isTouched && errMsgs">
        <p v-for="msg in errMsgs">{{ msg }}</p>
      </div>
    </div>
  </div>
</template>

<script>
import BaseCriterion from './BaseCriterion';

export default {
  extends: BaseCriterion,
  props: ['criterion', 'v', 'value', 'index'],
}
</script>
