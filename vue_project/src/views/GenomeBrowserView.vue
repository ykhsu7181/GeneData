<template>
  <div class="browser-page">
    <header class="browser-header">
      <div>
        <nav class="browser-breadcrumb" :aria-label="$t('page.genomeBrowser.breadcrumbLabel')">
          <router-link :to="assemblyRoute">{{ $t('page.genomeBrowser.assemblyDetail') }}</router-link>
          <span aria-hidden="true">/</span>
          <span>{{ $t('page.genomeBrowser.title') }}</span>
        </nav>
        <h1>{{ $t('page.genomeBrowser.titleWithAssembly', { assembly: assemblyLabel }) }}</h1>
        <p>{{ $t('page.genomeBrowser.description') }}</p>
      </div>
      <div class="browser-actions">
        <button class="secondary-button" type="button" @click="goBack">
          {{ $t('page.genomeBrowser.back') }}
        </button>
        <button class="secondary-button" type="button" :disabled="loading" @click="loadBrowser">
          {{ $t('common.refresh') }}
        </button>
        <a
          v-if="iframeUrl"
          class="primary-link"
          :href="iframeUrl"
          target="_blank"
          rel="noopener noreferrer"
        >
          {{ $t('page.genomeBrowser.openNewWindow') }}
        </a>
      </div>
    </header>

    <section v-if="loading" class="browser-state">
      <el-skeleton :rows="12" animated />
    </section>

    <section v-else-if="errorMessage" class="browser-state">
      <el-result icon="warning" :title="errorMessage">
        <template #extra>
          <button class="primary-button" type="button" @click="loadBrowser">
            {{ $t('page.genomeBrowser.retry') }}
          </button>
        </template>
      </el-result>
    </section>

    <section v-else class="browser-shell" :aria-busy="iframeLoading">
      <div v-if="iframeLoading" class="iframe-loading">
        {{ $t('page.genomeBrowser.loadingApplication') }}
      </div>
      <iframe
        v-if="iframeUrl"
        class="jbrowse-frame"
        :src="iframeUrl"
        :title="$t('page.genomeBrowser.frameTitle', { assembly: assemblyLabel })"
        allow="clipboard-write; fullscreen"
        allowfullscreen
        @load="iframeLoading = false"
      />
    </section>
  </div>
</template>

<script>
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import axios from 'axios';

const firstQueryValue = (value) => (Array.isArray(value) ? value[0] : value);

export default {
  name: 'GenomeBrowserView',
  setup() {
    const route = useRoute();
    const router = useRouter();
    const { t } = useI18n();
    const loading = ref(false);
    const iframeLoading = ref(false);
    const statusPayload = ref(null);
    const errorKey = ref('');

    const assemblyId = computed(() => String(route.params.assemblyId || '').trim());
    const annotationId = computed(() => String(firstQueryValue(route.query.annotation_id) || '').trim());
    const assemblyLabel = computed(() => (
      statusPayload.value?.assembly_code || `#${assemblyId.value || '-'}`
    ));
    const assemblyRoute = computed(() => ({
      name: 'assembly-detail',
      params: { assemblyId: assemblyId.value }
    }));
    const errorMessage = computed(() => (errorKey.value ? t(errorKey.value) : ''));
    const iframeUrl = computed(() => {
      const payload = statusPayload.value;
      if (!payload || !['ready', 'reference_only'].includes(payload.status)) return '';
      const configPath = `/gd/api/files/assemblies/${encodeURIComponent(assemblyId.value)}/jbrowse-config/`;
      const configUrl = new URL(configPath, window.location.origin);
      if (annotationId.value) configUrl.searchParams.set('annotation_id', annotationId.value);
      const params = new URLSearchParams({ config: configUrl.toString() });
      return `/jbrowse2/?${params.toString()}`;
    });

    const loadBrowser = async () => {
      if (!/^\d+$/.test(assemblyId.value)) {
        errorKey.value = 'page.genomeBrowser.invalidAssembly';
        return;
      }
      loading.value = true;
      iframeLoading.value = false;
      errorKey.value = '';
      statusPayload.value = null;
      try {
        const params = annotationId.value ? { annotation_id: annotationId.value } : {};
        const response = await axios.get(
          `/files/assemblies/${encodeURIComponent(assemblyId.value)}/jbrowse-status/`,
          { params }
        );
        const payload = response.data || {};
        if (!['ready', 'reference_only'].includes(payload.status)) {
          errorKey.value = `page.genomeBrowser.status.${payload.status || 'unknown'}`;
          return;
        }
        statusPayload.value = payload;
        iframeLoading.value = true;
      } catch (error) {
        errorKey.value = error.response?.status === 404
          ? 'page.genomeBrowser.notFound'
          : 'page.genomeBrowser.loadFailed';
      } finally {
        loading.value = false;
      }
    };
    const goBack = () => {
      const returnTo = String(firstQueryValue(route.query.return_to) || '').trim();
      if (returnTo.startsWith('/')) router.push(returnTo);
      else router.push(assemblyRoute.value);
    };

    watch([assemblyId, annotationId], loadBrowser, { immediate: true });

    return {
      assemblyLabel,
      assemblyRoute,
      errorMessage,
      goBack,
      iframeLoading,
      iframeUrl,
      loadBrowser,
      loading
    };
  }
};
</script>

<style scoped>
.browser-page { width:100%; padding:8px 0 30px; color:#15233d; box-sizing:border-box; }
.browser-header { display:flex; justify-content:space-between; gap:20px; margin-bottom:14px; padding:18px 20px; border:1px solid #e1e8f3; border-radius:13px; background:#fff; box-shadow:0 6px 18px rgba(35,68,116,.05); }
.browser-header h1 { margin:8px 0 5px; color:#102c5d; font-size:27px; }
.browser-header p { margin:0; color:#65758e; font-size:13px; }
.browser-breadcrumb { display:flex; align-items:center; gap:8px; color:#7a879b; font-size:13px; }
.browser-breadcrumb a { color:#3974c7; text-decoration:none; }
.browser-actions { display:flex; align-items:center; justify-content:flex-end; flex-wrap:wrap; gap:9px; }
.primary-link,.primary-button,.secondary-button { display:inline-flex; align-items:center; justify-content:center; min-height:38px; padding:0 15px; border-radius:8px; font:inherit; font-size:13px; font-weight:700; cursor:pointer; text-decoration:none; box-sizing:border-box; }
.primary-link,.primary-button { border:1px solid #176fe5; color:#fff; background:#176fe5; }
.secondary-button { border:1px solid #cdd9e8; color:#31557f; background:#fff; }
.secondary-button:disabled { opacity:.55; cursor:not-allowed; }
.browser-state,.browser-shell { min-height:620px; border:1px solid #dbe5f2; border-radius:13px; background:#fff; overflow:hidden; }
.browser-state { padding:24px; box-sizing:border-box; }
.browser-shell { position:relative; height:calc(100vh - 225px); min-height:680px; }
.iframe-loading { position:absolute; z-index:1; inset:0; display:grid; place-items:center; color:#5d7392; background:#f8fbff; }
.jbrowse-frame { display:block; width:100%; height:100%; border:0; background:#fff; }
@media (max-width:800px) { .browser-header { flex-direction:column; } .browser-actions { justify-content:flex-start; } .browser-shell { height:760px; min-height:760px; } }
</style>
