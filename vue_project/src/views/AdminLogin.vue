<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <h2>{{ $t('page.admin.title') }}</h2>
        <p>{{ $t('page.admin.loginTitle') }}</p>
      </div>
      
      <el-form 
        ref="loginForm" 
        :model="loginData" 
        :rules="loginRules" 
        class="login-form"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="loginData.username"
            :placeholder="$t('page.login.usernameRequired')"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input
            v-model="loginData.password"
            type="password"
            :placeholder="$t('page.login.passwordRequired')"
            prefix-icon="Lock"
            size="large"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            size="large" 
            :loading="loading"
            @click="handleLogin"
            class="login-button"
          >
            {{ loading ? $t('page.login.loggingIn') : $t('page.login.login') }}
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="login-footer">
        <p>{{ $t('page.admin.defaultAccount') }}</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useI18n } from 'vue-i18n'

export default {
  name: 'AdminLogin',
  setup() {
    const router = useRouter()
    const { t } = useI18n()
    const loading = ref(false)
    
    const loginData = reactive({
      username: '',
      password: ''
    })
    
    const loginRules = {
      username: [
        { required: true, message: t('page.login.usernameRequired'), trigger: 'blur' }
      ],
      password: [
        { required: true, message: t('page.login.passwordRequired'), trigger: 'blur' }
      ]
    }
    
    const loginForm = ref(null)

    const loadSession = async () => {
      try {
        const response = await axios.get('/admin/session/')
        if (response.data.authenticated) {
          router.replace('/admin/dashboard')
        }
      } catch (error) {
        console.error('检查管理员会话失败:', error)
      }
    }
    
    const handleLogin = async () => {
      if (!loginForm.value) return
      
      try {
        await loginForm.value.validate()
        loading.value = true

        // Ensure Django has issued the CSRF cookie before the unsafe request.
        await axios.get('/admin/session/')
        
        const response = await axios.post('/admin/login/', {
          username: loginData.username,
          password: loginData.password
        })
        
        if (response.data.success) {
          ElMessage.success(t('messages.loginSuccess'))
          router.push('/admin/dashboard')
        } else {
          ElMessage.error(t('messages.loginFailed'))
        }
      } catch (error) {
        console.error('登录错误:', error)
        if (error.response && error.response.data && error.response.data.message) {
          ElMessage.error(t('messages.loginFailed'))
        } else {
          ElMessage.error(t('messages.networkLoginFailed'))
        }
      } finally {
        loading.value = false
      }
    }

    onMounted(loadSession)
    
    return {
      loginData,
      loginRules,
      loginForm,
      loading,
      handleLogin
    }
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-box {
  width: 400px;
  padding: 40px;
  background: white;
  border-radius: 10px;
  box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-header h2 {
  color: #333;
  margin-bottom: 10px;
  font-size: 24px;
}

.login-header p {
  color: #666;
  margin: 0;
  font-size: 14px;
}

.login-form {
  margin-bottom: 20px;
}

.login-button {
  width: 100%;
  height: 45px;
  font-size: 16px;
}

.login-footer {
  text-align: center;
  color: #999;
  font-size: 12px;
}

.login-footer p {
  margin: 0;
}
</style>
