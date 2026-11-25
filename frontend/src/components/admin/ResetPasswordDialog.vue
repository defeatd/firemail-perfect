<template>
  <el-dialog
    :model-value="modelValue"
    :title="`重置密码 · ${user?.username || ''}`"
    :width="isMobile ? '94vw' : '440px'"
    :close-on-click-modal="false"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="fm-reset-dialog">
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
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="form.newPassword"
            type="password"
            show-password
            placeholder="至少 8 位字符"
            autocomplete="new-password"
          />
        </el-form-item>

        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            placeholder="再次输入新密码"
            autocomplete="new-password"
          />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <div class="fm-dialog-footer">
        <el-button @click="$emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确认重置</el-button>
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
  modelValue: { type: Boolean, default: false },
  user: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue', 'reset'])

const auth = useAuthStore()
const { isMobile } = useBreakpoint()

const formRef = ref(null)
const submitting = ref(false)
const errorMessage = ref('')

const form = reactive({
  newPassword: '',
  confirmPassword: ''
})

const rules = {
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '新密码长度不能少于 8 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, val, cb) => {
        if (val !== form.newPassword) cb(new Error('两次输入的密码不一致'))
        else cb()
      },
      trigger: 'blur'
    }
  ]
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) {
      form.newPassword = ''
      form.confirmPassword = ''
      errorMessage.value = ''
    }
  }
)

watch(
  () => form.newPassword,
  () => {
    if (form.confirmPassword) {
      formRef.value?.validateField('confirmPassword').catch(() => {})
    }
  }
)

async function handleSubmit() {
  if (!props.user) return
  errorMessage.value = ''
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return

  submitting.value = true
  try {
    await auth.resetUserPassword({
      userId: props.user.id,
      newPassword: form.newPassword
    })
    ElMessage.success('用户密码重置成功')
    emit('update:modelValue', false)
    emit('reset')
  } catch (err) {
    errorMessage.value = err?.response?.data?.error || err?.message || '重置密码失败'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.fm-reset-dialog {
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
