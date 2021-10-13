<script>
import SearchControlsAdditional from './SearchControlsAdditional';
import TheHeaderSiteTitle from './TheHeaderSiteTitle';
import TheHeaderNavigation from './TheHeaderNavigation';

export default {
  components: {
    SearchControlsAdditional,
    TheHeaderSiteTitle,
    TheHeaderNavigation,
  },

  computed: {
    isOnSearchPage() {
      return this.$route.matched.some(route => route.name === 'search');
    },

    isLoggedIn() {
      return this.$store.state.session.isLoggedIn;
    },

    isFullAccess() {
      return this.$store.state.session.isFullAccess;
    },
  },
};
</script>


<template>
  <header class="TheHeader">
    <the-header-siteTitle
      class="TheHeader-SiteTitle"
    />
    <searchControls-additional
      v-if="isOnSearchPage"
      class="TheHeader-SearchControls"
    />
    <the-header-navigation
      class="TheHeader-Navigation"
    />
  </header>
</template>


<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

@mixin navigation-on-line-with-page-title {
  @media (min-width: 410px) {
    @content;
  }
}

@mixin single-line-layout {
  @media (min-width: 950px) {
    @content;
  }
}

.TheHeader {
  $padding-y: $padding-small;

  display: flex;
  flex-direction: column;
  flex-wrap: nowrap;
  align-items: center;
  background-color: $color-grey-extra-light;
  padding-top: $padding-y;
  padding-bottom: $padding-medium;

  @include navigation-on-line-with-page-title {
    display: grid;
    grid:
      'siteTitle      navigation' auto
      'searchControls searchControls' auto
      / 1fr 1fr;
    grid-row-gap: $margin-extra-small;
    padding-bottom: $padding-y;
  }

  @include single-line-layout {
    display: flex;
    flex-direction: row;
    align-items: center;
    height: 70px;
  }
}

.TheHeader-SiteTitle {
  grid-area: siteTitle;
}

.TheHeader-SearchControls {
  grid-area: searchControls;
  margin-top: $margin-extra-small;

  @include navigation-on-line-with-page-title {
    margin-top: 0;
  }

  @include single-line-layout {
    margin-left: $margin-medium;
  }
}

.TheHeader-Navigation {
  grid-area: navigation;
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
  margin-top: $margin-small;

  @include navigation-on-line-with-page-title {
    margin-top: 0;
    margin-left: auto;
  }
}
</style>
