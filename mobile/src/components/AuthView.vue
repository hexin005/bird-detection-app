<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useOrchard } from '../store'

const props = defineProps<{ initialMode?: 'login' | 'register' | 'forgot' }>()
const store = useOrchard()
const mode = ref<'login' | 'register' | 'forgot'>(props.initialMode || 'login')
const form = reactive({
  server: store.server || 'http://192.168.1.10:8008',
  account: '',
  password: '',
  email: '',
  code: '',
  confirm: '',
  newPassword: '',
})
const demoCode = ref(''), sending = ref(false), countdown = ref(0), busy = ref(false)
let timer: ReturnType<typeof setInterval> | null = null
/* 密码小眼睛:每个密码框独立切换明文/密文 */
const eyes = reactive({ login: false, regPwd: false, regConfirm: false, resetPwd: false })
function toggleEye(key: keyof typeof eyes) { eyes[key] = !eyes[key] }

const emailOk = computed(() => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim().toLowerCase()))
const passwordOk = computed(() => form.newPassword.length >= 8)
const notify = (m: string) => uni.showToast({ title: m, icon: 'none', duration: 3000 })

function switchMode(next: 'login' | 'register' | 'forgot') {
  mode.value = next; demoCode.value = ''; stopCountdown()
}

async function run(action: () => Promise<unknown>) {
  if (busy.value) return
  busy.value = true
  try { await action() } catch (e) { notify((e as Error).message) } finally { busy.value = false }
}

function doLogin() {
  void run(async () => {
    await store.login(form.server, form.account.trim(), form.password)
    form.password = ''
  })
}

function startCountdown() {
  countdown.value = 60
  stopCountdown()
  timer = setInterval(() => { countdown.value -= 1; if (countdown.value <= 0) stopCountdown() }, 1000)
}
function stopCountdown() { if (timer) { clearInterval(timer); timer = null } }

function sendCode(purpose: 'register' | 'reset') {
  if (sending.value || countdown.value > 0) return
  if (!emailOk.value) { notify('请输入正确的邮箱地址'); return }
  void run(async () => {
    sending.value = true
    try {
      const result = await store.request<{ sent: boolean; demo: boolean; demo_code?: string }>('/auth/send-code', 'POST', { email: form.email.trim().toLowerCase(), purpose })
      if (result.demo && result.demo_code) { demoCode.value = result.demo_code; notify('演示模式:验证码已显示在横幅') }
      else { demoCode.value = ''; notify('验证码已发送至邮箱') }
      startCountdown()
    } finally { sending.value = false }
  })
}

function doRegister() {
  if (!emailOk.value) { notify('请输入正确的邮箱地址'); return }
  if (!/^\d{6}$/.test(form.code.trim())) { notify('请输入 6 位验证码'); return }
  if (form.password.length < 8) { notify('密码至少 8 位'); return }
  if (form.password !== form.confirm) { notify('两次输入的密码不一致'); return }
  void run(async () => {
    const email = form.email.trim().toLowerCase()
    await store.request('/auth/register', 'POST', { email, code: form.code.trim(), password: form.password })
    // 注册即登录:建立会话(resume + 同步),避免拿到 token 却停在注册页
    await store.login(form.server, email, form.password)
    demoCode.value = ''; stopCountdown()
  })
}

function doReset() {
  if (!emailOk.value) { notify('请输入正确的邮箱地址'); return }
  if (!/^\d{6}$/.test(form.code.trim())) { notify('请输入 6 位验证码'); return }
  if (form.newPassword.length < 8) { notify('新密码至少 8 位'); return }
  void run(async () => {
    await store.mutate('/auth/reset', 'POST', { email: form.email.trim().toLowerCase(), code: form.code.trim(), password: form.newPassword })
    notify('密码已重置，请用新密码登录')
    form.password = ''; form.newPassword = ''; form.code = ''
    switchMode('login')
  })
}
</script>

<template>
  <view class="qh-brand">
    <view class="qh-brand__mark">
      <svg width="30" height="34" viewBox="0 0 30 34" fill="none"><path d="M15 32V14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M15 20C15 12 9 7 2 6c1 8 5.5 13 13 14z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M15 16c0-7 5.5-11.5 13-12.5-1 8-5.5 12.5-13 12.5z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
    </view>
    <text class="qh-brand__title">{{ mode === 'login' ? '登录果园' : mode === 'register' ? '加入果园' : '找回密码' }}</text>
  </view>

  <view class="qh-auth-tabs" v-if="mode !== 'forgot'">
    <text :class="{ on: mode === 'login' }" @click="switchMode('login')">登 录</text>
    <text :class="{ on: mode === 'register' }" @click="switchMode('register')">注 册</text>
  </view>

  <!-- 演示验证码:持续横幅,避免 toast 转瞬即逝 -->
  <view v-if="demoCode" class="qh-auth-banner">演示验证码:{{ demoCode }} · 10 分钟内有效</view>

  <view v-if="mode === 'login'" class="qh-card">
    <text class="qh-auth-lbl">邮箱 / 用户名</text>
    <view class="qh-input"><input v-model="form.account" type="text" placeholder="邮箱或用户名" /></view>
    <text class="qh-auth-lbl">密码</text>
    <view class="qh-input"><input v-model="form.password" :type="eyes.login ? 'text' : 'password'" placeholder="请输入密码" /><button class="qh-eye" @click="toggleEye('login')"><svg width="16" height="16" viewBox="0 0 18 18" fill="none"><template v-if="eyes.login"><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" fill="currentColor"/></template><template v-else><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" stroke="currentColor" stroke-width="1.5"/><path d="M3 15.5L15.5 2.6" stroke="currentColor" stroke-width="1.5"/></template></svg></button></view>
    <view style="display:flex;justify-content:flex-end;margin-top:8px"><text class="qh-auth-link" @click="switchMode('forgot')">忘记密码?</text></view>
    <button class="qh-btn qh-btn--primary" style="margin-top:10px" :disabled="busy || !form.account || !form.password" @click="doLogin">{{ busy ? '正在连接…' : '登录并进入果园' }}</button>
  </view>

  <view v-else-if="mode === 'register'" class="qh-card">
    <text class="qh-auth-lbl">邮箱(作为登录账号)</text>
    <view class="qh-input"><input v-model="form.email" type="text" placeholder="you@example.com" /></view>
    <text class="qh-auth-lbl">验证码</text>
    <view class="qh-auth-code">
      <input v-model="form.code" type="text" placeholder="6 位数字" maxlength="6" />
      <text class="send" :class="{ off: countdown > 0 || sending || !emailOk }" @click="sendCode('register')">{{ countdown > 0 ? countdown + 's' : '获取验证码' }}</text>
    </view>
    <text class="qh-auth-lbl">设置密码</text>
    <view class="qh-input"><input v-model="form.password" :type="eyes.regPwd ? 'text' : 'password'" placeholder="至少 8 位" /><button class="qh-eye" @click="toggleEye('regPwd')"><svg width="16" height="16" viewBox="0 0 18 18" fill="none"><template v-if="eyes.regPwd"><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" fill="currentColor"/></template><template v-else><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" stroke="currentColor" stroke-width="1.5"/><path d="M3 15.5L15.5 2.6" stroke="currentColor" stroke-width="1.5"/></template></svg></button></view>
    <text class="qh-auth-lbl">确认密码</text>
    <view class="qh-input"><input v-model="form.confirm" :type="eyes.regConfirm ? 'text' : 'password'" placeholder="再次输入密码" /><button class="qh-eye" @click="toggleEye('regConfirm')"><svg width="16" height="16" viewBox="0 0 18 18" fill="none"><template v-if="eyes.regConfirm"><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" fill="currentColor"/></template><template v-else><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" stroke="currentColor" stroke-width="1.5"/><path d="M3 15.5L15.5 2.6" stroke="currentColor" stroke-width="1.5"/></template></svg></button></view>
    <button class="qh-btn qh-btn--primary" style="margin-top:14px" :disabled="busy" @click="doRegister">注册并登录</button>
  </view>

  <view v-else class="qh-card">
    <text class="qh-auth-lbl">注册邮箱</text>
    <view class="qh-input"><input v-model="form.email" type="text" placeholder="you@example.com" /></view>
    <text class="qh-auth-lbl">邮箱验证码</text>
    <view class="qh-auth-code">
      <input v-model="form.code" type="text" placeholder="6 位数字" maxlength="6" />
      <text class="send" :class="{ off: countdown > 0 || sending || !emailOk }" @click="sendCode('reset')">{{ countdown > 0 ? countdown + 's' : '发送验证码' }}</text>
    </view>
    <text class="qh-auth-lbl">新密码</text>
    <view class="qh-input"><input v-model="form.newPassword" :type="eyes.resetPwd ? 'text' : 'password'" placeholder="至少 8 位" /><button class="qh-eye" @click="toggleEye('resetPwd')"><svg width="16" height="16" viewBox="0 0 18 18" fill="none"><template v-if="eyes.resetPwd"><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" fill="currentColor"/></template><template v-else><path d="M1.5 9C3.5 5 6 3.4 9 3.4S14.5 5 16.5 9C14.5 13 12 14.6 9 14.6S3.5 13 1.5 9z" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="9" r="2.6" stroke="currentColor" stroke-width="1.5"/><path d="M3 15.5L15.5 2.6" stroke="currentColor" stroke-width="1.5"/></template></svg></button></view>
    <button class="qh-btn qh-btn--primary" style="margin-top:14px" :disabled="busy" @click="doReset">重置密码</button>
    <view style="text-align:center;margin-top:12px"><text class="qh-auth-link" @click="switchMode('login')">返回登录</text></view>
  </view>

  <view class="qh-card" v-if="mode === 'login'">
    <view style="display:flex;justify-content:space-between;align-items:center">
      <text class="qh-formlabel">服务地址(局域网)</text>
      <text class="qh-svcinfo" style="margin:0">{{ form.server.replace(/^https?:\/\//, '') }}</text>
    </view>
    <view class="qh-input" style="margin-top:8px;min-height:38px"><input v-model="form.server" type="text" placeholder="http://192.168.1.10:8008" /></view>
  </view>

  <text class="qh-auth-foot" style="display:block">没有账号?切换到「注册」,邮箱 + 验证码即可加入 · 密码 PBKDF2 加盐存储</text>
</template>
