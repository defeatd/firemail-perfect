<template>
  <div class="admin-navigation">
    <h3 class="nav-header">管理菜单</h3>
    <ul class="nav-links">
      <li>
        <router-link to="/admin/users">用户管理</router-link>
      </li>
      <li>
        <router-link to="/admin/users-simple">用户管理(简化版)</router-link>
      </li>
    </ul>
  </div>
</template>

<script>
export default {
  name: 'AdminNavigation'
}
</script>

<style scoped>
.admin-navigation {
  background-color: #f8f9fa;
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 20px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.nav-header {
  font-size: 18px;
  font-weight: 500;
  margin-bottom: 12px;
  color: #333;
  border-bottom: 1px solid #eaeaea;
  padding-bottom: 8px;
}

.nav-links {
  list-style: none;
  padding: 0;
  margin: 0;
}

.nav-links li {
  margin-bottom: 8px;
}

.nav-links a {
  display: block;
  padding: 8px 12px;
  color: var(--primary-color);
  text-decoration: none;
  border-radius: 4px;
  transition: all 0.3s;
}

.nav-links a:hover {
  background-color: #ecf5ff;
}

.nav-links a.router-link-active {
  background-color: var(--primary-color);
  color: white;
}
</style> 