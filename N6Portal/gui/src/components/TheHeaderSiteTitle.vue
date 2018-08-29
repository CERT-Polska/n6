<template>
  <!-- Site heading with logo -->
  <h1 class="TheHeader-Heading">
    <router-link
      class="TheHeader-HeadingLink"
      :to="{ name: 'main' }"
    >
      <span class="TheHeader-HeadingLinkText">
        Portal
      </span>
    </router-link>
  </h1>
</template>


<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

$heading-image-offset-y: 2px;

.TheHeader-Heading {
  font-weight: 700;
  font-size: $font-size-extra-large;
}

.TheHeader-HeadingLink {
  $background-width: 55px;
  $background-height: (122 / 165) * $background-width;

  display: flex;
  align-items: center;
  position: relative;
  top: -1 * $heading-image-offset-y;
  padding-left: $background-width + $margin-extra-small;
  height: $background-height;
  background-image: url('~@/images/logo.png');
  background-position: left center;
  background-size: $background-width $background-height;
  background-repeat: no-repeat;
}

.TheHeader-HeadingLinkText {
  position: relative;
  top: 1 * $heading-image-offset-y;
}
</style>
