<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useOrchard } from '../store'
import type { Me } from '../types'
import { THEMES, normalizeTheme } from '../theme'
import { alertRemindEnabled, setAlertRemind } from '../utils/alertNotify'
import ChangePassword from './ChangePassword.vue'

const emit = defineEmits<{ nav: [page: 'themes' | 'analytics' | 'guide'] }>()
const store = useOrchard()
const me = ref<Me | null>(null)
const error = ref('')
const uploading = ref(false), percent = ref(0)
const renameSheet = ref(false), renameValue = ref('')
const usernameSheet = ref(false), usernameValue = ref('')
const usernameError = ref('')
const changeSheet = ref(false)
const currentTheme = computed(() => normalizeTheme(me.value?.theme))
const remindOn = ref(alertRemindEnabled())
function onRemindChange(e: unknown) {
  const on = Boolean((e as { detail: { value: boolean } }).detail.value)
  setAlertRemind(on)
  remindOn.value = on
  notify(on ? '新告警提醒已开启' : '新告警提醒已关闭')
}
const themeMeta = computed(() => THEMES.find(t => t.id === currentTheme.value))
const avatarSrc = computed(() => me.value?.avatar ? store.server + me.value.avatar + '?ticket=' + encodeURIComponent(store.state?.media_ticket || '') : '')
const notify = (m: string) => uni.showToast({ title: m, icon: 'none', duration: 3000 })

async function load() {
  error.value = ''
  try { me.value = await store.request<Me>('/me') } catch (e) { error.value = (e as Error).message }
}
onMounted(load)
defineExpose({ load })

function pickAvatar() {
  // #ifdef H5
  const input = document.createElement('input')
  input.type = 'file'; input.accept = 'image/jpeg,image/png,image/webp'
  input.style.display = 'none'
  input.onchange = () => {
    const file = input.files?.[0]
    input.remove()
    if (!file) return
    if (file.size > 2 * 1024 * 1024) { notify('头像不能超过 2 MB'); return }
    uploading.value = true; percent.value = 0
    const xhr = new XMLHttpRequest()
    xhr.open('POST', store.server + '/api/avatar')
    xhr.timeout = 30000
    xhr.setRequestHeader('Authorization', 'Bearer ' + store.token)
    xhr.setRequestHeader('Content-Type', 'application/octet-stream')
    xhr.upload.onprogress = e => { if (e.lengthComputable) percent.value = Math.round(e.loaded / e.total * 100) }
    xhr.onload = () => {
      uploading.value = false
      try {
        const result = JSON.parse(xhr.responseText)
        if (xhr.status !== 200) throw new Error(result.detail)
        notify('头像已更新')
        void load()
      } catch (err) { notify((err as Error).message || '上传失败') }
    }
    xhr.onerror = xhr.ontimeout = () => { uploading.value = false; notify('上传中断，请重试') }
    xhr.send(file)
  }
  document.body.appendChild(input)
  input.click()
  // #endif
}

function previewAvatar() {
  if (avatarSrc.value) uni.previewImage({ urls: [avatarSrc.value], current: avatarSrc.value })
  else pickAvatar()
}
function openUsername() {
  usernameValue.value = me.value?.username || ''
  usernameError.value = ''
  usernameSheet.value = true
}
async function saveUsername() {
  const name = usernameValue.value.trim()
  if (!/^[A-Za-z0-9_\u4e00-\u9fff]{2,20}$/.test(name)) {
    usernameError.value = '用户名须为 2–20 个汉字、字母、数字或下划线'
    return
  }
  try {
    await store.mutate('/me/username', 'PUT', { username: name })
    usernameSheet.value = false
    notify('用户名已更新，可用于登录')
    await load()
  } catch (e) { usernameError.value = (e as Error).message }
}

function openRename() {
  renameValue.value = me.value?.display_name || ''
  renameSheet.value = true
}
async function saveRename() {
  const name = renameValue.value.trim()
  if (!name) { notify('昵称不能为空'); return }
  try {
    await store.mutate('/me', 'PUT', { display_name: name })
    renameSheet.value = false
    notify('昵称已更新')
    void load()
  } catch (e) { notify((e as Error).message) }
}

async function logout() {
  try { await store.logout() } catch { /* 本地会话照常清除 */ }
}

function onPasswordChanged() {
  changeSheet.value = false
}
</script>

<template>
  <view class="qh-header">
    <view class="qh-header__brand">
      <text class="qh-page-title">我的</text>
      <text class="qh-page-subtitle">账号 · 主题 · 观测报表</text>
    </view>
  </view>

  <!-- 用户信息卡 -->
  <view class="qh-window">
    <view class="qh-tbar"><view class="qh-tbar__box">×</view><text class="qh-tbar__t">果园守护人</text></view>
    <view class="qh-window__bd">
      <view class="qh-me-card">
        <view class="qh-me-avatar" @click="previewAvatar">
          <image v-if="avatarSrc" :src="avatarSrc" mode="aspectFill" />
          <text v-else style="font-size:10px;color:var(--ink-400)">无头像</text>
          <view class="qh-me-cam">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none"><circle cx="7" cy="7" r="4" stroke="currentColor" stroke-width="1.6"/><path d="m10 10 4 4" stroke="currentColor" stroke-width="1.6"/></svg>
          </view>
        </view>
        <view style="flex:1;min-width:0">
          <view class="qh-me-name">
            <text>{{ me?.display_name || me?.username || '…' }}</text>
            <text v-if="me?.username" class="qh-mvp">{{ me.username }}</text>
          </view>
          <text class="qh-me-mail">{{ me?.email || '未绑定邮箱' }}</text>
          <text class="qh-page-subtitle" style="font-size:10px;display:block;margin-top:2px">点头像可放大查看 · 昵称仅在本应用内显示</text>
        </view>
      </view>
      <view class="qh-me-actions">
        <button class="qh-btn qh-btn--secondary" style="flex:1" :disabled="uploading" @click="pickAvatar">
          <svg width="13" height="13" viewBox="0 0 16 16"><rect x="1" y="2" width="14" height="12" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M3 12l4-5 3 3 2-2 3 4z" fill="currentColor"/><circle cx="11" cy="6" r="1.5" fill="currentColor"/></svg>本地图片
        </button>
        <button class="qh-btn qh-btn--secondary" style="flex:1" @click="openUsername">设置用户名</button>
        <button class="qh-btn qh-btn--secondary" style="flex:1" @click="openRename">
          <svg width="13" height="13" viewBox="0 0 16 16"><path d="M2 12l1-3 7-7 2 2-7 7-3 1z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M9 3l2 2" stroke="currentColor" stroke-width="1.6"/></svg>改名
        </button>
      </view>
      <view v-if="uploading" class="qh-upload" style="margin-top:8px">
        <view class="qh-upload__top"><text class="qh-upload__label">{{ percent === 100 ? '处理中…' : '正在上传头像' }}</text><text class="qh-upload__pct">{{ percent }}%</text></view>
        <view class="qh-progress"><view class="qh-progress__bar" :style="{ width: percent + '%' }" /></view>
      </view>
      <text v-if="error" class="qh-note" style="display:block;text-align:left;margin-top:6px">{{ error }}</text>
    </view>
  </view>

  <!-- 主题入口 -->
  <view class="qh-window" style="cursor:pointer" @click="emit('nav', 'themes')">
    <view class="qh-tbar"><text class="qh-tbar__t">主题 · THEME</text></view>
    <view class="qh-window__bd">
      <view class="qh-me-row">
        <view style="flex:1;min-width:0">
          <view class="qh-alarmcard__title">{{ themeMeta?.label || '果园守护 1.0' }} <text class="qh-mvp">使用中</text></view>
          <text class="qh-page-subtitle" style="font-size:10px;display:block;margin-top:3px">共 2 套风格，大图预览一键切换，数据不受影响</text>
        </view>
        <text class="qh-chevron">›</text>
      </view>
    </view>
  </view>

  <!-- 鸟类知识库入口 -->
  <view class="qh-window" style="cursor:pointer" @click="emit('nav', 'guide')">
    <view class="qh-tbar"><text class="qh-tbar__t">鸟类知识库</text></view>
    <view class="qh-window__bd">
      <view class="qh-me-row">
        <view style="flex:1;min-width:0">
          <view class="qh-alarmcard__title">鸟类知识库</view>
          <text class="qh-page-subtitle" style="font-size:10px;display:block;margin-top:3px">13 种园内鸟种 · 科普档案 + 本园记录 · 可搜索</text>
        </view>
        <text class="qh-chevron">›</text>
      </view>
    </view>
  </view>

  <!-- 数据分析入口 -->
  <view class="qh-window" style="cursor:pointer" @click="emit('nav', 'analytics')">
    <view class="qh-tbar"><text class="qh-tbar__t">数据分析</text></view>
    <view class="qh-window__bd">
      <view class="qh-me-row">
        <view style="flex:1;min-width:0">
          <view class="qh-alarmcard__title">果园数据分析</view>
          <text class="qh-page-subtitle" style="font-size:10px;display:block;margin-top:3px">趋势 · 鸟种 · 时段 · 处理构成 · 驱离执行</text>
        </view>
        <svg class="qh-spark" width="72" height="26" viewBox="0 0 72 26"><polyline points="2,20 13,14 24,17 35,8 46,12 57,4 70,10" fill="none" stroke="currentColor" stroke-width="2"/><rect x="0" y="24" width="72" height="2" fill="currentColor"/></svg>
        <text class="qh-chevron">›</text>
      </view>
    </view>
  </view>

  <!-- 提醒设置(跨主题通用) -->
  <view class="qh-window">
    <view class="qh-tbar"><text class="qh-tbar__t">提醒 · ALERTS</text></view>
    <view class="qh-window__bd">
      <view class="qh-me-row">
        <view style="flex:1;min-width:0">
          <view class="qh-alarmcard__title">新告警提醒</view>
          <text class="qh-page-subtitle" style="font-size:10px;display:block;margin-top:3px">提示音 + 桌面通知 + 标题闪烁 · 桌面通知需浏览器授权</text>
        </view>
        <switch :checked="remindOn" :color="currentTheme === 'signal' ? '#d3212c' : '#111111'" @change="onRemindChange" />
      </view>
    </view>
  </view>

  <!-- 账号安全 -->
  <view class="qh-window">
    <view class="qh-tbar"><text class="qh-tbar__t">账号安全</text></view>
    <view class="qh-window__bd">
      <view class="qh-me-row" style="cursor:pointer" @click="changeSheet = true">
        <view style="flex:1">
          <view class="qh-alarmcard__title">修改密码</view>
          <text class="qh-page-subtitle" style="font-size:10px;display:block;margin-top:2px">修改后需用新密码重新登录</text>
        </view>
        <text class="qh-chevron">›</text>
      </view>
    </view>
  </view>

  <button class="qh-btn qh-btn--primary" @click="logout">退出登录</button>
  <text class="qh-svcinfo">System 1.0 · 青禾果园守护 · 数据来自果园服务</text>

  <!-- 用户名抽屉 -->
  <view v-if="usernameSheet" class="qh-mask qh-mask--bottom is-open" @click.self="usernameSheet = false">
    <view class="qh-sheet">
      <view class="qh-sheet__titlerow"><text class="qh-sheet__title">设置登录用户名</text><button class="qh-iconbtn--sm" aria-label="关闭用户名设置" @click="usernameSheet = false">×</button></view>
      <text class="qh-page-subtitle">2–20 个汉字、字母、数字或下划线；邮箱仍可登录和找回密码</text>
      <view class="qh-input"><input v-model="usernameValue" type="text" placeholder="输入新的用户名" maxlength="20" @input="usernameError = ''" /></view>
      <text v-if="usernameError" class="qh-note" style="color:var(--danger-fg)">{{ usernameError }}</text>
      <button class="qh-btn qh-btn--primary" @click="saveUsername">保存用户名</button>
    </view>
  </view>

  <!-- 改名抽屉 -->
  <view v-if="renameSheet" class="qh-mask qh-mask--bottom is-open" @click.self="renameSheet = false">
    <view class="qh-sheet">
      <view class="qh-sheet__titlerow">
        <text class="qh-sheet__title">修改昵称</text>
        <view class="qh-iconbtn--sm" @click="renameSheet = false"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></view>
      </view>
      <view class="qh-input"><input v-model="renameValue" type="text" placeholder="输入新的昵称" maxlength="32" /></view>
      <button class="qh-btn qh-btn--primary" @click="saveRename">保存</button>
    </view>
  </view>

  <!-- 修改密码抽屉 -->
  <ChangePassword v-if="changeSheet" @done="onPasswordChanged" @close="changeSheet = false" />
</template>
