<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useOrchard } from '../store'

const emit = defineEmits<{ done: [], close: [] }>()
const store = useOrchard()
const form = reactive({ old: '', next: '', confirm: '' })
const busy = ref(false)
const eyes = reactive({ old: false, next: false, confirm: false })
function toggleEye(key: keyof typeof eyes) { eyes[key] = !eyes[key] }
const notify = (m: string) => uni.showToast({ title: m, icon: 'none', duration: 3000 })

async function submit() {
  if (form.next.length < 8) { notify('新密码至少 8 位'); return }
  if (form.next !== form.confirm) { notify('两次输入的新密码不一致'); return }
  busy.value = true
  try {
    await store.mutate('/password/change', 'POST', { old_password: form.old, new_password: form.next })
    // 服务端已吊销全部会话(含当前),回到登录页
    await store.logout()
    emit('done')
    uni.showToast({ title: '密码已修改，请重新登录', icon: 'none', duration: 2500 })
  } catch (e) {
    notify((e as Error).message)
  } finally { busy.value = false }
}
</script>

<template>
  <view class="qh-mask qh-mask--bottom is-open" @click.self="emit('close')">
    <view class="qh-sheet">
      <view class="qh-sheet__titlerow">
        <text class="qh-sheet__title">修改密码</text>
        <view class="qh-iconbtn--sm" @click="emit('close')"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></view>
      </view>
      <view class="qh-paramrow">
        <view class="qh-paramrow__top"><text class="qh-paramrow__name">当前密码</text></view>
        <view class="qh-input"><input v-model="form.old" :type="eyes.old ? 'text' : 'password'" placeholder="输入当前密码" /><button class="qh-eye" @click="toggleEye('old')"><svg width="16" height="16" viewBox="0 0 18 18" fill="none"><template v-if="eyes.old"><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" fill="currentColor"/></template><template v-else><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" stroke="currentColor" stroke-width="1.5"/><path d="M3 15.5L15.5 2.6" stroke="currentColor" stroke-width="1.5"/></template></svg></button></view>
      </view>
      <view class="qh-paramrow">
        <view class="qh-paramrow__top"><text class="qh-paramrow__name">新密码</text><text class="qh-paramrow__value">至少 8 位</text></view>
        <view class="qh-input"><input v-model="form.next" :type="eyes.next ? 'text' : 'password'" placeholder="输入新密码" /><button class="qh-eye" @click="toggleEye('next')"><svg width="16" height="16" viewBox="0 0 18 18" fill="none"><template v-if="eyes.next"><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" fill="currentColor"/></template><template v-else><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" stroke="currentColor" stroke-width="1.5"/><path d="M3 15.5L15.5 2.6" stroke="currentColor" stroke-width="1.5"/></template></svg></button></view>
      </view>
      <view class="qh-paramrow">
        <view class="qh-paramrow__top"><text class="qh-paramrow__name">确认新密码</text></view>
        <view class="qh-input"><input v-model="form.confirm" :type="eyes.confirm ? 'text' : 'password'" placeholder="再次输入新密码" /><button class="qh-eye" @click="toggleEye('confirm')"><svg width="16" height="16" viewBox="0 0 18 18" fill="none"><template v-if="eyes.confirm"><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" fill="currentColor"/></template><template v-else><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" stroke="currentColor" stroke-width="1.5"/><path d="M3 15.5L15.5 2.6" stroke="currentColor" stroke-width="1.5"/></template></svg></button></view>
      </view>
      <text class="qh-hint">保存成功后将退出全部登录会话(含本机)，需用新密码重新登录。</text>
      <button class="qh-btn qh-btn--primary" :disabled="busy || !form.old || !form.next" @click="submit">{{ busy ? '正在保存…' : '确认修改' }}</button>
    </view>
  </view>
</template>
