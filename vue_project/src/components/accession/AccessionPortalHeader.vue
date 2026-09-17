<template>
  <header class="portal-header">
    <nav class="portal-breadcrumb" :aria-label="$t('page.accessionPortal.breadcrumbLabel')">
      <router-link to="/">{{ $t('nav.home') }}</router-link>
      <span aria-hidden="true">/</span>
      <span>{{ $t('nav.accession') }}</span>
    </nav>
    <h1>{{ $t('page.accessionPortal.title') }}</h1>
    <p>{{ $t('page.accessionPortal.subtitle') }}</p>
  </header>
</template>

<script>
export default {
  name: 'AccessionPortalHeader'
};
</script>

<style scoped>
.portal-header { margin-bottom:18px; }
.portal-breadcrumb { display:flex; align-items:center; gap:8px; margin-bottom:12px; color:#7183a0; font-size:13px; }
.portal-breadcrumb a { color:#2b6fc7; text-decoration:none; }
.portal-header h1 { margin:0; color:#102f61; font-size:34px; line-height:1.1; letter-spacing:-.03em; }
.portal-header p { margin:7px 0 0; color:#607698; font-size:14px; }
@media (max-width:700px) {
  .portal-header h1 { font-size:29px; }
}
</style>
