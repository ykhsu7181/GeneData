import { createApp } from 'vue'
import App from './App.vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import router from './router'
import axios from 'axios'
import i18n from './i18n'

// 设置axios的基本URL，确保请求发送到正确的端点
axios.defaults.baseURL = '/gd/api'

// 彻底解决ResizeObserver错误
// 方法1: 重写ResizeObserver
const _ResizeObserver = window.ResizeObserver;
window.ResizeObserver = class ResizeObserver extends _ResizeObserver {
  constructor(callback) {
    const wrappedCallback = (entries, observer) => {
      window.requestAnimationFrame(() => {
        try {
          callback(entries, observer);
        } catch (e) {
          // 忽略ResizeObserver相关错误
          if (!e.message.includes('ResizeObserver loop')) {
            throw e;
          }
        }
      });
    };
    super(wrappedCallback);
  }
};

// 方法2: 拦截所有相关错误
const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};

const originalConsoleError = window.console.error;
window.console.error = debounce((...args) => {
  const errorMessage = args[0]?.toString() || '';
  if (errorMessage.includes('ResizeObserver loop') ||
      errorMessage.includes('ResizeObserver loop completed') ||
      errorMessage.includes('undelivered notifications')) {
    return;
  }
  originalConsoleError.apply(window.console, args);
}, 100);

// 方法3: 全局错误处理
window.addEventListener('error', (event) => {
  const message = event.message || event.error?.message || '';
  if (message.includes('ResizeObserver') ||
      message.includes('undelivered notifications')) {
    event.stopImmediatePropagation();
    event.preventDefault();
    return false;
  }
}, true);

window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason?.toString() || '';
  if (reason.includes('ResizeObserver') ||
      reason.includes('undelivered notifications')) {
    event.preventDefault();
    return false;
  }
});

// 全局axios
const app = createApp(App)
app.config.globalProperties.$axios = axios

// 使用插件
app.use(ElementPlus)
app.use(router)
app.use(i18n)

// 全局错误处理
app.config.errorHandler = (err, vm, info) => {
  if (err.message &&
      (err.message.includes('ResizeObserver loop') ||
       err.message.includes('ResizeObserver loop completed'))) {
    return;
  }
  console.error(err);
};

app.mount('#app')

// 根据环境设置baseURL
let baseURL = ''
if (process.env.NODE_ENV === 'production') {
  // 生产环境使用域名
  baseURL = 'https://riceome.hzau.edu.cn/gd/'
} else {
  // 开发环境使用本地地址
  baseURL = 'http://localhost:8080/'
}