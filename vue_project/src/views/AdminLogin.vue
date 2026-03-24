<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <h2>基因数据管理系统</h2>
        <p>管理员登录</p>
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
            placeholder="请输入用户名"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input
            v-model="loginData.password"
            type="password"
            placeholder="请输入密码"
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
            {{ loading ? '登录中...' : '登录' }}
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="login-footer">
        <p>默认账号：root / root123</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'

export default {
  name: 'AdminLogin',
  setup() {
    const router = useRouter()
    const loading = ref(false)
    
    const loginData = reactive({
      username: '',
      password: ''
    })
    
    const loginRules = {
      username: [
        { required: true, message: '请输入用户名', trigger: 'blur' }
      ],
      password: [
        { required: true, message: '请输入密码', trigger: 'blur' }
      ]
    }
    
    const loginForm = ref(null)
    
    const handleLogin = async () => {
      if (!loginForm.value) return
      
      try {
        await loginForm.value.validate()
        loading.value = true
        
        const response = await axios.post('/admin/login/', {
          username: loginData.username,
          password: loginData.password
        })
        
        if (response.data.success) {
          // 保存token到localStorage
          localStorage.setItem('admin_token', response.data.token)
          localStorage.setItem('admin_user', JSON.stringify(response.data.user))
          
          ElMessage.success('登录成功')
          router.push('/admin/dashboard')
        } else {
          ElMessage.error(response.data.message || '登录失败')
        }
      } catch (error) {
        console.error('登录错误:', error)
        if (error.response && error.response.data && error.response.data.message) {
          ElMessage.error(error.response.data.message)
        } else {
          ElMessage.error('登录失败，请检查网络连接')
        }
      } finally {
        loading.value = false
      }
    }
    
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
