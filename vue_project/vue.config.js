const { defineConfig } = require('@vue/cli-service')
const jbrowseProxyTarget = process.env.GENEDATA_JBROWSE_PROXY_TARGET || 'http://localhost:18088'
const djangoProxyTarget = process.env.GENEDATA_DJANGO_PROXY_TARGET || 'http://localhost:2025'

module.exports = defineConfig({
  transpileDependencies: true,
  lintOnSave: false,
  // 设置部署路径为/gb/，与旧数据仓库保持一致
  publicPath: process.env.NODE_ENV === 'production' ? '/gb/' : '/',
  // 生产环境构建配置
  productionSourceMap: false,
  devServer: {
    proxy: {
      '/jbrowse2': {
        target: jbrowseProxyTarget,
        changeOrigin: true
      },
      '/gd/api/files/browser-assets': {
        target: jbrowseProxyTarget,
        changeOrigin: true
      },
      '/gd/api': {
        target: djangoProxyTarget,
        changeOrigin: true,
        pathRewrite: {
          '^/gd/api': '/gd/api'
        }
      }
    }
  }
})
