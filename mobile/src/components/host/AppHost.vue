<script setup lang="ts">
// AppHost:稳定业务宿主。持有跨主题状态与统一语义动作,provide 给主题布局/页面;
// 主题切换只替换布局组件,本组件不卸载 → 页面位置/上传/指令/弹窗规则可控。
import { computed, onMounted, provide, ref, watch } from 'vue'
import { createHost, hostKey, time, names, clock, alarmClass } from './hostContext'
import { useWorkspace } from './useWorkspace'
import { useOrchard } from '../../store'
import type { Preferences } from '../../types'
import type { ThemeId } from '../../theme'
import BLayout from './layouts/BLayout.vue'
import TowerLayout from './layouts/TowerLayout.vue'
import SignalLayout from './layouts/SignalLayout.vue'
import PixelLayout from './layouts/PixelLayout.vue'
import MeHome from '../MeHome.vue'
import ThemePicker from '../ThemePicker.vue'
import Analytics from '../Analytics.vue'

const store = useOrchard()
const host = createHost()
const workspace = useWorkspace(store)
provide(hostKey, host)

const meHomeRef = ref<{ load: () => Promise<void> } | null>(null)
const analyticsRef = ref<{ load: () => Promise<void> } | null>(null)

defineExpose({ host })

// 登录/登出:会话级清理 + 工作区重置;登录后按账号偏好恢复主题。
// AppHost 在 token 变 true 后才挂载(v-if),onMounted 兜底首次登录,watch 覆盖后续登出/登录。
async function onTokenChanged(token?: string) {
  host.onTokenChange(token)
  workspace.reset()
  if (token) {
    try {
      const me = await store.request<{ theme: ThemeId }>('/me')
      host.setTheme(me.theme === 'tower' || me.theme === 'pixel' ? 'b1bit' : me.theme) // setTheme 内部同步应用 DOM 与全局缓存
    } catch { /* me 拉取失败不阻塞进入 */ }
  }
}
onMounted(() => { if (store.token) void onTokenChanged(store.token) })
watch(() => store.token, token => { void onTokenChanged(token) })

// 告警状态变化:确认弹窗里关联的告警被处理后,清理关联并提示
watch(() => host.s?.alarms.find(a => a.id === host.selectedAlarm)?.status, st => {
  if (st && st !== 'new') host.selectedAlarm = null
})

// 页面进入按需刷新(我的/分析为常驻组件)
function onPageEnter(p: string) {
  if (p === 'me') meHomeRef.value?.load()
  if (p === 'analytics') analyticsRef.value?.load()
  if (p === 'monitor' || p === 'me') void host.refreshToday()
  if (p === 'control') void host.run(host.loadAutomation)
  if (p === 'records') void host.loadRecordsSummary()
}
watch(() => host.page, onPageEnter, { immediate: true })

const layouts = { b1bit: BLayout, tower: TowerLayout, signal: SignalLayout, pixel: PixelLayout } as const
const layout = computed(() => layouts[host.theme] || BLayout)
const overlayPage = computed(() => ['me', 'themes', 'analytics'].includes(host.page) ? host.page : '')
function updatePreference(key: 'confidence' | 'consecutive' | 'cooldown', value: number) {
  if (!Number.isFinite(value)) return
  if (key === 'confidence') host.preferences.confidence = Math.min(.95, Math.max(.1, value / 100))
  else if (key === 'consecutive') host.preferences.consecutive = Math.min(10, Math.max(1, Math.round(value)))
  else host.preferences.cooldown = Math.min(300, Math.max(1, Math.round(value)))
}

</script>

<template>
  <!-- 覆盖视图:我的 / 主题 / 数据分析(布局无关,主题 token 已换肤)。
       置于布局组件之前,保证 overlay 显示时 dock 仍沉底(flex 尾部)。 -->
  <view class="page" :class="{ 'is-current': overlayPage === 'me' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__back" @click="host.nav('monitor')">◂ 返回</text>
        <svg width="16" height="13" viewBox="0 0 16 13" fill="none"><path d="M2 11V6L6 2h6l2 3v6h-3V8H5v3z" fill="currentColor"/><rect x="6" y="4" width="2" height="2" style="fill:var(--surface-card)"/></svg>
        <text class="qh-menubar__ttl">果园守护</text>
        <text class="qh-menubar__item">文件</text>
        <text class="qh-menubar__item">监测</text>
        <text class="qh-menubar__item">告警</text>
        <text class="qh-menubar__item">特效</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><MeHome ref="meHomeRef" @nav="host.nav" /></view>
  </view>

  <view class="page" :class="{ 'is-current': overlayPage === 'themes' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__back" @click="host.nav('me')">◂ 返回</text>
        <svg width="16" height="13" viewBox="0 0 16 13" fill="none"><path d="M2 11V6L6 2h6l2 3v6h-3V8H5v3z" fill="currentColor"/><rect x="6" y="4" width="2" height="2" style="fill:var(--surface-card)"/></svg>
        <text class="qh-menubar__ttl">主题</text>
        <text class="qh-menubar__item">大图预览</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><ThemePicker :current="host.theme" @apply="host.setTheme" /></view>
  </view>

  <view class="page" :class="{ 'is-current': overlayPage === 'analytics' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__back" @click="host.nav('me')">◂ 返回</text>
        <svg width="16" height="13" viewBox="0 0 16 13" fill="none"><path d="M2 11V6L6 2h6l2 3v6h-3V8H5v3z" fill="currentColor"/><rect x="6" y="4" width="2" height="2" style="fill:var(--surface-card)"/></svg>
        <text class="qh-menubar__ttl">数据分析</text>
        <text class="qh-menubar__item">东区 · 01 号监控点</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><Analytics ref="analyticsRef" /></view>
  </view>

  <!-- 主题布局(四核心页 + dock,dock 沉底) -->
  <component :is="layout" />

  <!-- ======================= 弹窗:设置 ======================= -->
  <view v-if="host.modal === 'mSet'" class="qh-mask qh-mask--bottom is-open" @click.self="host.modal = ''">
    <view class="qh-sheet">
      <view class="qh-sheet__grab"/>
      <view class="qh-sheet__titlerow"><text class="qh-sheet__title">设置</text><view class="qh-iconbtn--sm" @click="host.modal = ''"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></view></view>
      <text style="font-size:var(--text-base);font-weight:500;color:var(--ink-900);">场景切换</text>
      <view v-for="opt in [{id:'normal',name:'正常执行',desc:'识别到鸟类后人工确认驱离'},{id:'offline',name:'设备离线',desc:'演示设备不在线时的界面与提示'},{id:'timeout',name:'执行超时',desc:'演示指令无响应时的状态与恢复'}]" :key="opt.id" class="qh-radio" :class="{ 'is-selected': host.preferences.scenario === opt.id }" @click="host.preferences.scenario = opt.id as Preferences['scenario']">
        <view class="qh-radio__circle"><view class="qh-radio__dot"/></view>
        <view class="qh-radio__info"><text class="qh-radio__name">{{ opt.name }}</text><text class="qh-radio__desc">{{ opt.desc }}</text></view>
      </view>
      <view class="qh-paramrow"><view class="qh-paramrow__top"><text class="qh-paramrow__name">置信度阈值</text><text class="qh-paramrow__value">{{ host.preferences.confidence.toFixed(2) }}</text></view><slider :min="10" :max="95" :step="5" :value="Math.round(host.preferences.confidence * 100)" activeColor="var(--accent)" backgroundColor="var(--ink-100)" @change="updatePreference('confidence', Number($event.detail.value))" /></view>
      <view class="qh-paramrow"><view class="qh-paramrow__top"><text class="qh-paramrow__name">连续检出帧数</text><text class="qh-paramrow__value">{{ host.preferences.consecutive }} 帧</text></view><slider :min="1" :max="10" :step="1" :value="host.preferences.consecutive" activeColor="var(--accent)" backgroundColor="var(--ink-100)" @change="updatePreference('consecutive', Number($event.detail.value))" /></view>
      <view class="qh-paramrow"><view class="qh-paramrow__top"><text class="qh-paramrow__name">事件合并间隔</text><text class="qh-paramrow__value">{{ host.preferences.cooldown }} 秒</text></view><slider :min="1" :max="300" :step="1" :value="host.preferences.cooldown" activeColor="var(--accent)" backgroundColor="var(--ink-100)" @change="updatePreference('cooldown', Number($event.detail.value))" /></view>
      <button class="qh-btn qh-btn--primary" :disabled="host.store.busy || !!host.store.active" @click="host.run(async() => { await host.store.mutate('/settings','PUT',host.preferences); host.modal=''; host.notify('设置已保存') })">保存设置</button>
      <view class="qh-logoutrow"><text style="color:var(--danger-fg)" @click="host.run(() => host.store.logout())">退出登录</text><text style="color:var(--brand-500)" @click="host.run(() => host.store.logout())">更换服务</text></view>
      <text class="qh-svcinfo">服务 {{ host.store.server }} · 视频 HLS · 推理 {{ host.s?.monitor.device || 'cpu' }} · {{ host.s?.monitor.sample_fps || 2 }} 帧/秒抽样</text>
    </view>
  </view>

  <!-- ======================= 弹窗:告警详情 ======================= -->
  <view v-if="host.modal === 'mAlarm' && host.alarm" class="qh-mask qh-mask--center is-open" @click.self="host.modal = ''">
    <view class="qh-dialog">
      <view class="qh-dialog__titlerow"><text class="qh-dialog__title">告警详情</text><button class="qh-iconbtn--sm" aria-label="关闭告警详情" @click="host.modal = ''">×</button></view>
      <image class="qh-detailimg" :src="host.store.media('captures/' + host.alarm!.snapshot)" mode="aspectFill"/>
      <view class="qh-dialog__titlerow"><text class="qh-dialog__title">{{ host.alarm!.species }} · {{ host.alarm!.count }} 只</text><text :class="alarmClass(host.alarm!.status)">{{ names(host.alarm!.status) }}</text></view>
      <view class="qh-infogrid">
        <view class="qh-infogrid__row">
          <view class="qh-infocell"><text class="qh-infocell__label">置信度</text><text class="qh-infocell__value">{{ (host.alarm!.confidence * 100).toFixed(0) }}%</text></view>
          <view class="qh-infocell"><text class="qh-infocell__label">发现时间</text><text class="qh-infocell__value">{{ clock(host.alarm!.at) }}</text></view>
        </view>
        <view class="qh-infogrid__row">
          <view class="qh-infocell"><text class="qh-infocell__label">录像位置</text><text class="qh-infocell__value">{{ host.alarm!.video_time.toFixed(1) }}s</text></view>
          <view class="qh-infocell"><text class="qh-infocell__label">监控点</text><text class="qh-infocell__value">东区·01</text></view>
        </view>
      </view>
      <view class="qh-btnrow">
        <button class="qh-btn qh-btn--half qh-btn--ghost-danger" :disabled="host.store.busy" @click="host.alarm!.status === 'new' ? host.run(async() => { await host.store.mutate('/alarms/' + host.alarm!.id + '/ignore'); host.modal = '' }) : host.replayAlarm(host.alarm!)">{{ host.alarm!.status === 'new' ? '忽略' : '回看视频' }}</button>
        <button class="qh-btn qh-btn--half qh-btn--primary" :disabled="host.store.busy" @click="host.alarm!.status === 'new' ? host.handle() : host.modal = ''">{{ host.alarm!.status === 'new' ? '确认驱离' : '关闭' }}</button>
      </view>
    </view>
  </view>

  <!-- ======================= 弹窗:确认执行 ======================= -->
  <view v-if="host.modal === 'mConfirm'" class="qh-mask qh-mask--center is-open" @click.self="host.modal = ''">
    <view class="qh-dialog">
      <view style="width:44px;height:44px;background:var(--warn-bg);color:var(--warn-fg);display:flex;align-items:center;justify-content:center;">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M3 8v4h3l4 3.5v-11L6 8H3z" fill="currentColor"/><path d="M13 7a4.5 4.5 0 010 6M15.5 5a8 8 0 010 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      </view>
      <text class="qh-dialog__title">确认执行驱离？</text>
      <text class="qh-dialog__desc">{{ host.activeMode.desc }}</text>
      <view class="qh-confinfo">
        <view class="qh-confinfo__row"><text class="qh-confinfo__label">执行时长</text><text class="qh-confinfo__value">{{ host.duration }} 秒 · 定时结束</text></view>
        <view class="qh-confinfo__row"><text class="qh-confinfo__label">关联事件</text><text class="qh-confinfo__value">{{ host.selectedAlarm || '手动操作' }}</text></view>
        <view class="qh-confinfo__row"><text class="qh-confinfo__label">执行设备</text><text class="qh-confinfo__value">{{ host.activeMode.device }} · {{ host.offline ? '离线' : '在线' }}</text></view>
      </view>
      <view class="qh-btnrow">
        <button class="qh-btn qh-btn--half qh-btn--ghost-danger" @click="host.modal = ''">取消</button>
        <button class="qh-btn qh-btn--half qh-btn--primary" :disabled="host.store.busy" @click="host.run(host.execute)">{{ host.store.busy ? '正在提交…' : '确认执行' }}</button>
      </view>
      <text class="qh-confnote">模拟执行器 · 不会控制真实硬件</text>
    </view>
  </view>

  <!-- ======================= 弹窗:操作记录 ======================= -->
  <view v-if="host.modal === 'mLog' && host.command" class="qh-mask qh-mask--bottom is-open" @click.self="host.modal = ''">
    <view class="qh-sheet">
      <view class="qh-sheet__grab"/>
      <view class="qh-sheet__titlerow">
        <view><text class="qh-sheet__title">操作记录</text><text style="display:block;font-size:var(--text-xs);color:var(--ink-400);margin-top:3px;">{{ host.command!.id }}<text v-if="host.command!.alarm_id"> · {{ host.command!.alarm_id }}</text></text></view>
        <view class="qh-iconbtn--sm" @click="host.modal = ''"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></view>
      </view>
      <view class="qh-tl">
        <view class="qh-tl__item"><view class="qh-tl__dot qh-tl__dot--confirm"/><view class="qh-tl__info"><view class="qh-tl__head"><text class="qh-tl__title">人工确认</text><text class="qh-tl__time">{{ time(host.command!.at) }}</text></view><text class="qh-tl__msg">确认了下发一次 {{ host.command!.duration }} 秒驱离操作</text></view></view>
        <view class="qh-tl__item"><view class="qh-tl__dot" :class="host.command!.started_at ? 'qh-tl__dot--running' : 'qh-tl__dot--confirm'"/><view class="qh-tl__info"><view class="qh-tl__head"><text class="qh-tl__title">{{ host.command!.started_at ? '开始执行' : '尚未执行' }}</text><text v-if="host.command!.started_at" class="qh-tl__time">{{ time(host.command!.started_at) }}</text></view><text class="qh-tl__msg">{{ host.command!.mode === 'infrared' ? '红外驱鸟器 02' : host.command!.mode === 'both' ? '双模驱离系统（声学+红外）' : '声学驱鸟器 01' }} · 时长 {{ host.command!.duration }} 秒 · 定时结束</text></view></view>
        <view class="qh-tl__item"><view class="qh-tl__dot" :class="host.command!.status === 'completed' ? 'qh-tl__dot--done' : host.command!.status === 'failed' ? 'qh-tl__dot--confirm' : 'qh-tl__dot--running'"/><view class="qh-tl__info"><view class="qh-tl__head"><text class="qh-tl__title">{{ names(host.command!.status) }}</text><text v-if="host.command!.ended_at" class="qh-tl__time">{{ time(host.command!.ended_at) }}</text></view><text class="qh-tl__msg">{{ host.command!.message }}</text></view></view>
      </view>
      <text class="qh-svcinfo">{{ host.command!.status === 'completed' ? '此记录只证明模拟指令完成，不代表真实驱鸟成功' : '未完成的操作不会将告警标记为已处理' }}</text>
    </view>
  </view>
</template>
