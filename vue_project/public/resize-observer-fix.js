// 彻底解决ResizeObserver错误的脚本
(function() {
  'use strict';
  
  // 方法1: 重写ResizeObserver构造函数
  if (window.ResizeObserver) {
    const OriginalResizeObserver = window.ResizeObserver;
    
    window.ResizeObserver = class extends OriginalResizeObserver {
      constructor(callback) {
        const wrappedCallback = (entries, observer) => {
          try {
            // 使用requestAnimationFrame来避免循环
            requestAnimationFrame(() => {
              try {
                callback(entries, observer);
              } catch (e) {
                // 静默处理ResizeObserver错误
                if (e.message && e.message.includes('ResizeObserver loop')) {
                  return;
                }
                throw e;
              }
            });
          } catch (e) {
            // 静默处理所有ResizeObserver相关错误
            if (!e.message || !e.message.includes('ResizeObserver')) {
              throw e;
            }
          }
        };
        
        super(wrappedCallback);
      }
    };
  }
  
  // 方法2: 拦截错误事件
  const originalAddEventListener = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function(type, listener, options) {
    if (type === 'error') {
      const wrappedListener = function(event) {
        if (event.message && event.message.includes('ResizeObserver')) {
          event.stopImmediatePropagation();
          event.preventDefault();
          return false;
        }
        return listener.call(this, event);
      };
      return originalAddEventListener.call(this, type, wrappedListener, options);
    }
    return originalAddEventListener.call(this, type, listener, options);
  };
  
  // 方法3: 全局错误处理
  window.addEventListener('error', function(event) {
    if (event.message && (
        event.message.includes('ResizeObserver loop') ||
        event.message.includes('undelivered notifications')
    )) {
      event.stopImmediatePropagation();
      event.preventDefault();
      return false;
    }
  }, true);
  
  // 方法4: 控制台错误拦截
  const originalConsoleError = console.error;
  console.error = function(...args) {
    const message = args[0]?.toString() || '';
    if (message.includes('ResizeObserver') || 
        message.includes('undelivered notifications')) {
      return;
    }
    return originalConsoleError.apply(console, args);
  };
  
  // 方法5: Promise错误处理
  window.addEventListener('unhandledrejection', function(event) {
    const reason = event.reason?.toString() || '';
    if (reason.includes('ResizeObserver') || 
        reason.includes('undelivered notifications')) {
      event.preventDefault();
      return false;
    }
  });
  
})();
