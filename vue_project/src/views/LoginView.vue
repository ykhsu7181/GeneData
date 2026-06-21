<template>
  <div class="login-container">
    <div class="login-box">
      <h2>基因组数据仓库</h2>
      <div class="login-form">
        <el-form :model="loginForm" :rules="loginRules" ref="loginFormRef">
          <el-form-item prop="username">
            <el-input 
              v-model="loginForm.username" 
              placeholder="用户名" 
              prefix-icon="el-icon-user">
            </el-input>
          </el-form-item>
          <el-form-item prop="password">
            <el-input 
              v-model="loginForm.password" 
              type="password" 
              placeholder="密码" 
              prefix-icon="el-icon-lock" 
              show-password>
            </el-input>
          </el-form-item>
          <el-form-item>
            <el-button 
              type="primary" 
              :loading="loading" 
              @click="handleLogin" 
              style="width: 100%">
              登录
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

export default {
  name: 'LoginView',
  setup() {
    const router = useRouter()
    const loginFormRef = ref(null)
    const loading = ref(false)
    
    const loginForm = reactive({
      username: '',
      password: ''
    })
    
    const loginRules = {
      username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
      password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
    }
    
    const handleLogin = () => {
      loginFormRef.value.validate((valid) => {
        if (valid) {
          loading.value = true
          
          // 简单的硬编码验证
          if (loginForm.username === 'root' && loginForm.password === 'root123') {
            // 保存登录状态到 localStorage
            localStorage.setItem('isLoggedIn', 'true')
            
            // 登录成功提示
            ElMessage({
              message: '登录成功',
              type: 'success'
            })
            
            // 跳转到首页
            router.push('/dashboard')
          } else {
            ElMessage.error('用户名或密码错误')
          }
          
          loading.value = false
        }
      })
    }
    
    return {
      loginForm,
      loginRules,
      loginFormRef,
      loading,
      handleLogin
    }
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f5f7fa;
}

.login-box {
  width: 400px;
  padding: 40px;
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.login-box h2 {
  text-align: center;
  margin-bottom: 30px;
  color: #409EFF;
}

.login-form {
  margin-top: 20px;
}
</style> 
