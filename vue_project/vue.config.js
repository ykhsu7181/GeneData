const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  transpileDependencies: true,
  lintOnSave: false,
  // 设置部署路径为/gb/，与旧数据仓库保持一致
  publicPath: process.env.NODE_ENV === 'production' ? '/gb/' : '/',
  // 生产环境构建配置
  productionSourceMap: false,
  devServer: {
    proxy: {
      '/gd/api': {
        target: 'http://localhost:2025',
        changeOrigin: true,
        pathRewrite: {
          '^/gd/api': '/gd/api'
        }
      }
    }
  }
})
