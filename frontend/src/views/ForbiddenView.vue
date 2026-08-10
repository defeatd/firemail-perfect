<template>
  <div class="forbidden-container">
    <div class="forbidden-box">
      <div class="forbidden-icon">
        <i class="material-icons">block</i>
      </div>
      <h1>禁止访问</h1>
      <p>您没有权限访问此页面</p>
      <div class="actions">
        <router-link to="/" class="btn btn-primary">返回首页</router-link>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ForbiddenView'
}
</script>

<style scoped>
.forbidden-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 80px);
  padding: 20px;
}

.forbidden-box {
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  padding: 30px;
  text-align: center;
  max-width: 500px;
  width: 100%;
}

.forbidden-icon {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}

.forbidden-icon i {
  font-size: 80px;
  color: #dc3545;
}

h1 {
  font-size: 24px;
  color: #333;
  margin-bottom: 16px;
}

p {
  color: #666;
  margin-bottom: 30px;
}

.actions {
  margin-top: 20px;
}

.btn {
  display: inline-block;
  padding: 10px 20px;
  font-size: 16px;
  font-weight: 500;
  text-align: center;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s, opacity 0.3s;
  border: none;
  text-decoration: none;
}

.btn-primary {
  background-color: #42b983;
  color: white;
}

.btn-primary:hover {
  background-color: #3aa876;
}
</style> 