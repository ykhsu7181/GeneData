<template>
  <div class="browser-page">
    <header class="browser-header">
      <div class="browser-heading">
        <nav class="browser-breadcrumb" :aria-label="$t('page.genomeBrowser.breadcrumbLabel')">
          <router-link :to="assemblyRoute">{{ $t('page.genomeBrowser.assemblyDetail') }}</router-link>
          <span aria-hidden="true">/</span>
          <span>{{ $t('page.genomeBrowser.title') }}</span>
        </nav>
        <div class="browser-title-line">
          <h1>{{ $t('page.genomeBrowser.titleWithAssembly', { assembly: assemblyLabel }) }}</h1>
          <span class="browser-product-badge">JBrowse 2</span>
        </div>
      </div>
      <div class="browser-actions">
        <button class="secondary-button" type="button" @click="goBack">
          <el-icon aria-hidden="true"><ArrowLeft /></el-icon>
          <span>{{ backLabel }}</span>
        </button>
        <button
          class="icon-button"
          type="button"
          :disabled="loading"
          :aria-label="$t('page.genomeBrowser.reloadBrowser')"
          :title="$t('page.genomeBrowser.reloadBrowser')"
          @click="loadBrowser"
        >
          <el-icon aria-hidden="true"><Refresh /></el-icon>
        </button>
        <a
          v-if="iframeUrl"
          class="secondary-link"
          :href="iframeUrl"
          target="_blank"
          rel="noopener noreferrer"
        >
          <el-icon aria-hidden="true"><TopRight /></el-icon>
          <span>{{ $t('page.genomeBrowser.openNewWindow') }}</span>
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
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ArrowLeft, Refresh, TopRight } from '@element-plus/icons-vue';
import axios from 'axios';
import { normalizeInternalAppPath } from '@/utils/internalNavigation';
import {
  buildJBrowseUrl,
  normalizeJBrowseLocation,
  normalizePositiveId
} from '@/utils/jbrowseNavigation';

const firstQueryValue = (value) => (Array.isArray(value) ? value[0] : value);
const isCanceledRequest = error => (
  error?.code === 'ERR_CANCELED'
  || error?.name === 'CanceledError'
  || axios.isCancel?.(error)
);

export default {
  name: 'GenomeBrowserView',
  components: { ArrowLeft, Refresh, TopRight },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const { t } = useI18n();
    const loading = ref(false);
    const iframeLoading = ref(false);
    const statusPayload = ref(null);
    const errorKey = ref('');
    let statusController = null;
    let requestToken = 0;
    let componentDisposed = false;

    const assemblyId = computed(() => String(route.params.assemblyId || '').trim());
    const rawAnnotationId = computed(() => String(firstQueryValue(route.query.annotation_id) || '').trim());
    const annotationId = computed(() => normalizePositiveId(rawAnnotationId.value));
    const rawLocation = computed(() => String(firstQueryValue(route.query.loc) || '').trim());
    const requestedLocation = computed(() => normalizeJBrowseLocation(rawLocation.value));
    const assemblyLabel = computed(() => (
      statusPayload.value?.assembly_code || `#${assemblyId.value || '-'}`
    ));
    const assemblyRoute = computed(() => ({
      name: 'assembly-detail',
      params: { assemblyId: assemblyId.value }
    }));
    const safeReturnPath = computed(() => normalizeInternalAppPath(route.query.return_to));
    const backLabel = computed(() => (
      safeReturnPath.value.startsWith('/annotation')
        ? t('page.genomeBrowser.backToAnnotation')
        : t('page.genomeBrowser.backToAssembly')
    ));
    const errorMessage = computed(() => (errorKey.value ? t(errorKey.value) : ''));
    const iframeUrl = computed(() => {
      const payload = statusPayload.value;
      if (!payload || !['ready', 'reference_only'].includes(payload.status)) return '';
      const configPath = `/gd/api/files/assemblies/${encodeURIComponent(assemblyId.value)}/jbrowse-config/`;
      const configUrl = new URL(configPath, window.location.origin);
      if (annotationId.value) configUrl.searchParams.set('annotation_id', annotationId.value);
      if (!requestedLocation.value) {
        return buildJBrowseUrl({ configUrl: configUrl.toString() });
      }
      if (payload.status !== 'ready') return '';
      return buildJBrowseUrl({
        configUrl: configUrl.toString(),
        assemblyName: payload.assembly_name || '',
        loc: requestedLocation.value,
        trackIds: Array.isArray(payload.track_ids) ? payload.track_ids : []
      });
    });

    const loadBrowser = async () => {
      const token = requestToken + 1;
      requestToken = token;
      statusController?.abort();
      statusController = null;
      if (!normalizePositiveId(assemblyId.value)) {
        errorKey.value = 'page.genomeBrowser.invalidAssembly';
        return;
      }
      if (rawAnnotationId.value && !annotationId.value) {
        errorKey.value = 'page.genomeBrowser.invalidAnnotation';
        return;
      }
      if (rawLocation.value && !requestedLocation.value) {
        errorKey.value = 'page.genomeBrowser.invalidLocation';
        return;
      }
      const controller = new AbortController();
      statusController = controller;
      loading.value = true;
      iframeLoading.value = false;
      errorKey.value = '';
      statusPayload.value = null;
      try {
        const params = annotationId.value ? { annotation_id: annotationId.value } : {};
        const response = await axios.get(
          `/files/assemblies/${encodeURIComponent(assemblyId.value)}/jbrowse-status/`,
          { params, signal: controller.signal }
        );
        if (componentDisposed || controller.signal.aborted || token !== requestToken) return;
        const payload = response.data || {};
        if (!['ready', 'reference_only'].includes(payload.status)) {
          errorKey.value = `page.genomeBrowser.status.${payload.status || 'unknown'}`;
          return;
        }
        if (
          requestedLocation.value
          && (
            payload.status !== 'ready'
            || !payload.assembly_name
            || !Array.isArray(payload.track_ids)
            || !payload.track_ids.length
          )
        ) {
          errorKey.value = 'page.genomeBrowser.locationUnavailable';
          return;
        }
        statusPayload.value = payload;
        if (!iframeUrl.value) {
          statusPayload.value = null;
          errorKey.value = 'page.genomeBrowser.invalidLocation';
          return;
        }
        iframeLoading.value = true;
      } catch (error) {
        if (isCanceledRequest(error) || controller.signal.aborted) return;
        if (token !== requestToken) return;
        errorKey.value = error.response?.status === 404
          ? 'page.genomeBrowser.notFound'
          : 'page.genomeBrowser.loadFailed';
      } finally {
        if (statusController === controller && token === requestToken) {
          loading.value = false;
          statusController = null;
        }
      }
    };
    const goBack = () => {
      const returnTo = safeReturnPath.value;
      if (returnTo) router.push(returnTo);
      else router.push(assemblyRoute.value);
    };

    watch([assemblyId, rawAnnotationId, rawLocation], loadBrowser, { immediate: true });

    onBeforeUnmount(() => {
      componentDisposed = true;
      requestToken += 1;
      statusController?.abort();
    });

    return {
      assemblyLabel,
      assemblyRoute,
      backLabel,
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
.browser-page { width:100%; padding:8px 0 36px; color:#15233d; box-sizing:border-box; }
.browser-header { display:flex; align-items:center; justify-content:space-between; gap:18px; margin-bottom:16px; padding:16px 20px 18px; border:1px solid #e1e8f3; border-radius:13px; background:#fff; box-shadow:0 6px 18px rgba(35,68,116,.05); }
.browser-heading { min-width:0; }
.browser-title-line { display:flex; align-items:center; flex-wrap:wrap; gap:12px; margin:0; }
.browser-header h1 { margin:0; color:#102c5d; font-size:24px; line-height:1.2; }
.browser-product-badge { display:inline-flex; align-items:center; min-height:24px; padding:0 8px; border:1px solid #d8e3f0; border-radius:999px; color:#55708f; background:#f6f9fd; font-size:11px; font-weight:700; }
.browser-breadcrumb { display:flex; align-items:center; gap:8px; margin-bottom:6px; color:#76849a; font-size:13px; }
.browser-breadcrumb a { color:#3974c7; text-decoration:none; }
.browser-actions { display:flex; align-items:center; justify-content:flex-end; flex-shrink:0; gap:7px; }
.primary-button,.secondary-button,.secondary-link,.icon-button { display:inline-flex; align-items:center; justify-content:center; min-height:34px; border-radius:7px; font:inherit; font-size:12px; font-weight:700; cursor:pointer; text-decoration:none; box-sizing:border-box; }
.primary-button { padding:0 14px; border:1px solid #176fe5; color:#fff; background:#176fe5; }
.secondary-button,.secondary-link,.icon-button { border:1px solid #d4deea; color:#31557f; background:#fff; }
.secondary-button,.secondary-link { gap:6px; padding:0 11px; }
.icon-button { width:34px; padding:0; }
.secondary-button:hover,.secondary-link:hover,.icon-button:hover { border-color:#9bbbe3; color:#176fe5; background:#f7faff; }
.secondary-button:disabled,.icon-button:disabled { opacity:.55; cursor:not-allowed; }
.browser-state,.browser-shell { border:1px solid #dbe5f2; border-radius:10px; background:#fff; overflow:hidden; }
.browser-state { padding:24px; box-sizing:border-box; }
.browser-state { min-height:480px; }
.browser-shell { position:relative; height:calc(100vh - 294px); height:calc(100dvh - 294px); min-height:480px; }
.iframe-loading { position:absolute; z-index:1; inset:0; display:grid; place-items:center; color:#5d7392; background:#f8fbff; }
.jbrowse-frame { display:block; width:100%; height:100%; border:0; background:#fff; }
@media (max-width:800px) { .browser-header { align-items:flex-start; flex-direction:column; } .browser-actions { justify-content:flex-start; } .browser-shell { height:calc(100vh - 342px); height:calc(100dvh - 342px); min-height:420px; } }
@media (max-width:520px) { .browser-actions { width:100%; flex-wrap:wrap; } .secondary-button,.secondary-link { flex:1; } .browser-header h1 { font-size:21px; } }
</style>
