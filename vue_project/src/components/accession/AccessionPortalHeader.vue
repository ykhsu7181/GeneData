<template>
  <header class="portal-header">
    <nav class="portal-breadcrumb" :aria-label="$t('page.accessionPortal.breadcrumbLabel')">
      <router-link to="/">{{ $t('nav.home') }}</router-link>
      <span aria-hidden="true">/</span>
      <span>{{ $t('nav.accession') }}</span>
    </nav>
    <h1>{{ $t('page.accessionPortal.title') }}</h1>
  </header>
</template>

<script>
export default {
  name: 'AccessionPortalHeader'
};
</script>

<style scoped>
.portal-header { margin-bottom:12px; padding-top:4px; }
.portal-breadcrumb { display:flex; align-items:center; gap:8px; margin-bottom:8px; color:#7183a0; font-size:13px; }
.portal-breadcrumb a { color:#2b6fc7; text-decoration:none; }
.portal-header h1 { margin:0; color:#102f61; font-size:30px; line-height:1.12; letter-spacing:-.03em; }
@media (max-width:700px) {
  .portal-header h1 { font-size:26px; }
}
</style>
