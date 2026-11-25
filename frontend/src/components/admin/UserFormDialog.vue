<template>
  <el-dialog
    :model-value="modelValue"
    title="添加用户"
    :width="isMobile ? '94vw' : '440px'"
    :close-on-click-modal="false"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="fm-user-dialog">
      <el-alert
        v-if="errorMessage"
        type="error"
        :closable="false"
        show-icon
        :title="errorMessage"
      />

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleSubmit"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="3-20 个字符" autocomplete="off" />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="至少 8 位字符"
            autocomplete="new-password"
          />
        </el-form-item>

        <el-form-item>
          <el-checkbox v-model="form.is_admin">授予管理员权限</el-checkbox>
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <div class="fm-dialog-footer">
        <el-button @click="$emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">创建</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useBreakpoint } from '@/composables/useBreakpoint'

const props = defineProps({
  modelValue: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'created'])

const auth = useAuthStore()
const { isMobile } = useBreakpoint()

const formRef = ref(null)
const submitting = ref(false)
const errorMessage = ref('')

const form = reactive({
  username: '',
  password: '',
  is_admin: false
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度须在 3 到 20 个字符之间', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码长度不能少于 8 个字符', trigger: 'blur' }
  ]
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) {
      form.username = ''
      form.password = ''
      form.is_admin = false
      errorMessage.value = ''
    }
  }
)

async function handleSubmit() {
  errorMessage.value = ''
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return

  submitting.value = true
  try {
    await auth.createUser({
      username: form.username.trim(),
      password: form.password,
      is_admin: form.is_admin
    })
    ElMessage.success('用户创建成功')
    emit('update:modelValue', false)
    emit('created')
  } catch (err) {
    errorMessage.value = err?.response?.data?.error || err?.message || '创建用户失败'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.fm-user-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-3);
}

.fm-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--fm-space-2);
}
</style>
