<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useOrchard } from '../../store'
import VideoWorkspace from '../../components/VideoWorkspace.vue'
import VideoLibrary from '../../components/VideoLibrary.vue'
import BirdAlarms from '../../components/BirdAlarms.vue'
import type { Alarm, Command, Event, Preferences } from '../../types'

const store = useOrchard()
const page = ref('monitor'), modal = ref(''), selectedAlarm = ref<string | null>(null)
const recordMode = ref('videos'), archiveTask = ref(''), archiveTime = ref(0), archiveNonce = ref(0)
const detailId = ref(''), recordFilter = ref('all'), duration = ref(5)
const credentials = reactive({ server: store.server, username: 'orchard', password: '' })
const preferences = reactive<Preferences>({ scenario: 'normal', confidence: .45, consecutive: 3, cooldown: 60 })
const older = ref<Event[]>([]), historyEnd = ref(false)
const fetchedAlarm = ref<Alarm | null>(null), fetchedCommand = ref<Command | null>(null)

const s = computed(() => store.state)
const alarm = computed(() => s.value?.alarms.find(a => a.id === detailId.value) || (fetchedAlarm.value?.id === detailId.value ? fetchedAlarm.value : null))
const command = computed(() => s.value?.commands.find(c => c.id === detailId.value) || (fetchedCommand.value?.id === detailId.value ? fetchedCommand.value : null))
const pending = computed(() => s.value?.alarms.filter(a => a.status === 'new') || [])
const events = computed(() => {
  const unique = new Map<number, Event>()
  for (const e of [...older.value, ...(s.value?.events || [])]) unique.set(e.id, e)
  return [...unique.values()].sort((a,b) => b.id - a.id).filter(e => recordFilter.value === 'all' || (recordFilter.value === 'detection' ? e.kind === 'detection' : e.kind !== 'detection'))
})
const running = computed(() => ['starting', 'running', 'stopping'].includes(s.value?.monitor.status || ''))
const remaining = computed(() => store.active ? Math.min(store.active.duration, Math.max(0, Math.ceil(store.active.duration - (store.now - (store.active.started_at || store.now))))) : 0)
const offline = computed(() => s.value?.settings.scenario === 'offline')

const statusNames: Record<string,string> = { new:'待处理', processing:'执行中', handled:'已处理', ignored:'已忽略', pending:'待执行', running:'执行中', completed:'已完成', failed:'执行超时', cancelled:'已停止', unknown:'结果未知', idle:'未开始', starting:'加载模型', stopping:'正在停止', stopped:'已停止', ended:'检测完成', interrupted:'服务中断', error:'检测异常' }
const names = (v: string) => statusNames[v] || v
const time = (v: number) => new Date(v * 1000).toLocaleString('zh-CN', { hour12:false })
const clock = (v: number) => new Date(v * 1000).toLocaleTimeString('zh-CN', { hour12:false, hour:'2-digit', minute:'2-digit' })
const shortTime = (v: number) => new Date(v * 1000).toLocaleString('zh-CN', { hour12:false, month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' })
const notify = (m: string) => uni.showToast({ title: m, icon:'none', duration:3000 })

/* 徽标映射：监控 8 态 / 告警 4 态 / 指令 6 态，全部落到 demo 的 qh-badge 体系 */
const monBadge: Record<string,string> = { idle:'neutral', starting:'info', running:'running', stopping:'info', stopped:'neutral', ended:'ended', interrupted:'new', error:'failed' }
const monClass = (st: string) => 'qh-badge qh-badge--' + (monBadge[st] || 'ended')
const alarmClass = (st: string) => 'qh-badge qh-badge--' + st
const badgeText = (st: string) => st === 'running' ? '正在监测' : names(st)

async function run(action: () => Promise<unknown>) {
  if (store.busy) return
  store.busy = true
  try { await action() } catch(e) { notify((e as Error).message) } finally { store.busy = false }
}
function go(v: string) { if(v !== 'records') archiveTask.value=''; page.value = v; uni.pageScrollTo({ scrollTop:0, duration:0 }) }
function openAlarm(a: Alarm) { fetchedAlarm.value = a; detailId.value = a.id; modal.value = 'mAlarm' }
function replayAlarm(a: Alarm) { modal.value=''; recordMode.value='videos'; archiveTask.value=a.task_id; archiveTime.value=a.video_time; archiveNonce.value++; go('records') }
function settings() { if (s.value) Object.assign(preferences, s.value.settings); modal.value = 'mSet' }
function openScene() { if (typeof window !== 'undefined') window.open('/scene/', '_blank') }
function handle() { selectedAlarm.value = detailId.value; modal.value = 'mConfirm' }
async function execute() { await store.command(duration.value, selectedAlarm.value); modal.value = ''; selectedAlarm.value = null; notify('已提交至模拟执行器') }
async function inspectEvent(e: Event) {
  const isAlarm = e.ref_id.startsWith('A')
  if (!(isAlarm ? s.value?.alarms : s.value?.commands)?.find(x => x.id === e.ref_id)) {
    const row = await store.request<Alarm | Command>('/detail/' + (isAlarm ? 'alarms' : 'commands') + '/' + e.ref_id)
    if (isAlarm) fetchedAlarm.value = row as Alarm
    else fetchedCommand.value = row as Command
  }
  detailId.value = e.ref_id; modal.value = isAlarm ? 'mAlarm' : 'mLog'
}
async function loadHistory() {
  const before = Math.min(...[...older.value, ...(s.value?.events || [])].map(e=>e.id))
  const result = await store.request<{items:Event[]}>('/history?kind=events&before=' + before)
  older.value.push(...result.items); historyEnd.value = result.items.length < 100
}

watch(() => store.token, () => { modal.value = ''; older.value = []; selectedAlarm.value = null; fetchedAlarm.value = fetchedCommand.value = null })
watch(() => s.value?.alarms.find(a => a.id === selectedAlarm.value)?.status, st => { if (st && st !== 'new') selectedAlarm.value = null })
</script>

<template>
  <view class="phone" id="app">

    <!-- ======================= 登录页 ======================= -->
    <view class="page page--nologin" :class="{ 'is-current': !store.token }">
      <view class="statusbar">
        <text class="time">9:41</text>
        <view class="icons">
          <svg width="18" height="12" viewBox="0 0 18 12" fill="none"><rect y="7" width="3" height="5" rx="1" fill="#232B1D"/><rect x="5" y="5" width="3" height="7" rx="1" fill="#232B1D"/><rect x="10" y="2.5" width="3" height="9.5" rx="1" fill="#232B1D"/><rect x="15" width="3" height="12" rx="1" fill="#232B1D"/></svg>
          <svg width="17" height="12" viewBox="0 0 17 12" fill="none"><path d="M1 4a11 11 0 0115 0M3.7 6.8a7 7 0 019.6 0M6.4 9.4a3.2 3.2 0 014.2 0" stroke="#232B1D" stroke-width="1.6" stroke-linecap="round"/><circle cx="8.5" cy="10.5" r="1.2" fill="#232B1D"/></svg>
          <svg width="25" height="12" viewBox="0 0 25 12" fill="none"><rect x=".5" y=".5" width="21" height="11" rx="3" stroke="#232B1D" stroke-opacity=".4"/><rect x="2" y="2" width="15" height="8" rx="1.5" fill="#232B1D"/></svg>
        </view>
      </view>
      <view class="page__content">
        <view class="qh-brand">
          <view class="qh-brand__mark">
            <svg width="30" height="34" viewBox="0 0 30 34" fill="none"><path d="M15 32V14" stroke="#F5F7EC" stroke-width="2" stroke-linecap="round"/><path d="M15 20C15 12 9 7 2 6c1 8 5.5 13 13 14z" stroke="#F5F7EC" stroke-width="2" stroke-linejoin="round"/><path d="M15 16c0-7 5.5-11.5 13-12.5-1 8-5.5 12.5-13 12.5z" stroke="#F5F7EC" stroke-width="2" stroke-linejoin="round"/></svg>
          </view>
          <text class="qh-brand__title">青禾 · 果园守护</text>
          <text class="qh-brand__tag">欢迎回来，开启今天的巡护</text>
        </view>
        <text class="qh-formlabel">连接你的果园监测服务</text>
        <view class="qh-input"><input v-model="credentials.server" type="text" placeholder="http://192.168.1.23:8008" /></view>
        <view class="qh-input"><input v-model="credentials.username" type="text" placeholder="请输入账号" /></view>
        <view class="qh-input"><input v-model="credentials.password" type="password" placeholder="请输入密码" /></view>
        <button class="qh-btn qh-btn--primary" :disabled="store.busy || !credentials.password" @click="run(async () => { await store.login(credentials.server, credentials.username, credentials.password); credentials.password = '' })">{{ store.busy ? '正在连接…' : '登录并进入果园' }}</button>
        <text class="qh-hint">账号由本地服务创建。手机访问时，请填写电脑的局域网地址，并确保手机与电脑处于同一网络。</text>
        <view class="qh-footer"><text>MVP · 仅限局域网使用 · v0.2</text></view>
      </view>
    </view>

    <!-- ======================= 监控页 ======================= -->
    <view class="page" :class="{ 'is-current': store.token && page === 'monitor' }">
      <view class="statusbar">
        <text class="time">9:41</text>
        <view class="icons">
          <svg width="18" height="12" viewBox="0 0 18 12" fill="none"><rect y="7" width="3" height="5" rx="1" fill="#232B1D"/><rect x="5" y="5" width="3" height="7" rx="1" fill="#232B1D"/><rect x="10" y="2.5" width="3" height="9.5" rx="1" fill="#232B1D"/><rect x="15" width="3" height="12" rx="1" fill="#232B1D"/></svg>
          <svg width="17" height="12" viewBox="0 0 17 12" fill="none"><path d="M1 4a11 11 0 0115 0M3.7 6.8a7 7 0 019.6 0M6.4 9.4a3.2 3.2 0 014.2 0" stroke="#232B1D" stroke-width="1.6" stroke-linecap="round"/><circle cx="8.5" cy="10.5" r="1.2" fill="#232B1D"/></svg>
          <svg width="25" height="12" viewBox="0 0 25 12" fill="none"><rect x=".5" y=".5" width="21" height="11" rx="3" stroke="#232B1D" stroke-opacity=".4"/><rect x="2" y="2" width="15" height="8" rx="1.5" fill="#232B1D"/></svg>
        </view>
      </view>
      <view class="page__content">
        <view class="qh-header">
          <view class="qh-header__brand">
            <view class="qh-header__row"><text class="qh-appname">青禾示范果园</text><text class="qh-mvp">MVP</text></view>
            <text class="qh-site">东区 · 01 号监控点</text>
          </view>
          <view class="qh-header__actions"><button class="qh-3dbtn" @click="openScene"><text>3D 视角</text></button><button class="qh-iconbtn" @click="settings"><svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" stroke="#44523E" stroke-width="1.5"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33h.01a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51h.01a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82v.01a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z" stroke="#44523E" stroke-width="1.5"/></svg></button></view>
        </view>

        <view class="qh-conn"><view class="qh-conn__left"><view class="qh-conn__dot"/><text>{{ store.connection }}</text></view><text class="qh-conn__src">{{ s ? '数据来自果园服务' : '等待同步' }}</text></view>

        <view class="qh-titleblock">
          <view class="qh-titlerow">
            <text class="qh-page-title">果园，尽在掌握</text>
            <view :class="monClass(s?.monitor.status || 'idle')"><view class="qh-badge__dot"/><text class="qh-badge__text">{{ badgeText(s?.monitor.status || 'idle') }}</text></view>
          </view>
          <text class="qh-page-subtitle">今日巡护，从这里开始</text>
        </view>

        <VideoWorkspace />

        <view class="qh-stats">
          <view class="qh-stat"><text class="qh-stat__num qh-stat__num--warn">{{ s?.counts.pending || 0 }}</text><text class="qh-stat__label">待处理告警</text></view>
          <view class="qh-stat"><text class="qh-stat__num">{{ s?.counts.total || 0 }}</text><text class="qh-stat__label">检测事件</text></view>
          <view class="qh-stat"><text class="qh-stat__num">{{ s?.counts.completed || 0 }}</text><text class="qh-stat__label">模拟执行完成</text></view>
        </view>

        <view v-if="pending.length" class="qh-card qh-alarmcard" style="cursor:pointer" @click="openAlarm(pending[0])">
          <view class="qh-alarmcard__top">
            <image class="qh-thumb" :src="store.media('captures/' + pending[0].snapshot)" mode="aspectFill"/>
            <view class="qh-alarmcard__mid">
              <view class="qh-alarmcard__titlerow"><text class="qh-alarmcard__title">发现 {{ pending[0].count }} 只{{ pending[0].species }}</text><text class="qh-badge qh-badge--new">待处理</text></view>
              <text class="qh-alarmcard__meta">东区 · 01 号监控点 · {{ shortTime(pending[0].at) }}</text>
            </view>
          </view>
          <view class="qh-alarmcard__bottom">
            <text class="qh-alarmcard__stat">录像 {{ pending[0].video_time.toFixed(1) }} 秒 · 置信度 {{ (pending[0].confidence * 100).toFixed(0) }}%</text>
            <text class="qh-link">查看并处理 <text class="qh-chevron">›</text></text>
          </view>
        </view>

        <view class="qh-devicebar">
          <view class="qh-devicebar__icon"><svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M2.5 7v4h3l4 3.5v-11L5.5 7h-3z" stroke="#44523E" stroke-width="1.4" stroke-linejoin="round"/><path d="M12 6.5a3.5 3.5 0 010 5M14 4.5a6.3 6.3 0 010 9" stroke="#44523E" stroke-width="1.4" stroke-linecap="round"/></svg></view>
          <view class="qh-devicebar__info"><text class="qh-devicebar__name">声学驱鸟器 01</text><text class="qh-devicebar__desc">模拟设备 · 人工确认后执行</text></view>
          <view class="qh-pill"><view class="qh-pill__dot"/><text class="qh-pill__text">{{ offline ? '离线' : '在线' }}</text></view>
        </view>
      </view>
    </view>

    <!-- ======================= 告警页 ======================= -->
    <view class="page" :class="{ 'is-current': store.token && page === 'alarms' }">
      <view class="statusbar">
        <text class="time">9:41</text>
        <view class="icons">
          <svg width="18" height="12" viewBox="0 0 18 12" fill="none"><rect y="7" width="3" height="5" rx="1" fill="#232B1D"/><rect x="5" y="5" width="3" height="7" rx="1" fill="#232B1D"/><rect x="10" y="2.5" width="3" height="9.5" rx="1" fill="#232B1D"/><rect x="15" width="3" height="12" rx="1" fill="#232B1D"/></svg>
          <svg width="17" height="12" viewBox="0 0 17 12" fill="none"><path d="M1 4a11 11 0 0115 0M3.7 6.8a7 7 0 019.6 0M6.4 9.4a3.2 3.2 0 014.2 0" stroke="#232B1D" stroke-width="1.6" stroke-linecap="round"/><circle cx="8.5" cy="10.5" r="1.2" fill="#232B1D"/></svg>
          <svg width="25" height="12" viewBox="0 0 25 12" fill="none"><rect x=".5" y=".5" width="21" height="11" rx="3" stroke="#232B1D" stroke-opacity=".4"/><rect x="2" y="2" width="15" height="8" rx="1.5" fill="#232B1D"/></svg>
        </view>
      </view>
      <view class="page__content"><BirdAlarms @open="openAlarm" /></view>
    </view>

    <!-- ======================= 控制页 ======================= -->
    <view class="page" :class="{ 'is-current': store.token && page === 'control' }">
      <view class="statusbar">
        <text class="time">9:41</text>
        <view class="icons">
          <svg width="18" height="12" viewBox="0 0 18 12" fill="none"><rect y="7" width="3" height="5" rx="1" fill="#232B1D"/><rect x="5" y="5" width="3" height="7" rx="1" fill="#232B1D"/><rect x="10" y="2.5" width="3" height="9.5" rx="1" fill="#232B1D"/><rect x="15" width="3" height="12" rx="1" fill="#232B1D"/></svg>
          <svg width="17" height="12" viewBox="0 0 17 12" fill="none"><path d="M1 4a11 11 0 0115 0M3.7 6.8a7 7 0 019.6 0M6.4 9.4a3.2 3.2 0 014.2 0" stroke="#232B1D" stroke-width="1.6" stroke-linecap="round"/><circle cx="8.5" cy="10.5" r="1.2" fill="#232B1D"/></svg>
          <svg width="25" height="12" viewBox="0 0 25 12" fill="none"><rect x=".5" y=".5" width="21" height="11" rx="3" stroke="#232B1D" stroke-opacity=".4"/><rect x="2" y="2" width="15" height="8" rx="1.5" fill="#232B1D"/></svg>
        </view>
      </view>
      <view class="page__content">
        <view class="qh-header">
          <view class="qh-header__row">
            <text class="qh-page-title">远程控制</text>
            <text class="qh-badge qh-badge--new">模拟执行</text>
          </view>
        </view>

        <view class="qh-devicecard">
          <view class="qh-orbit">
            <view class="qh-orbit__ring"/>
            <view class="qh-orbit__core"><svg width="22" height="22" viewBox="0 0 18 18" fill="none"><path d="M2.5 7v4h3l4 3.5v-11L5.5 7h-3z" stroke="#F5F7EC" stroke-width="1.4" stroke-linejoin="round"/><path d="M12 6.5a3.5 3.5 0 010 5M14 4.5a6.3 6.3 0 010 9" stroke="#F5F7EC" stroke-width="1.4" stroke-linecap="round"/></svg></view>
            <svg class="qh-orbit__wave" style="left:2px;" width="14" height="20" viewBox="0 0 14 20" fill="none"><path d="M11 3Q4 10 11 17M7 6.5Q3.5 10 7 13.5" stroke="#7B9B63" stroke-width="1.5" stroke-linecap="round"/></svg>
            <svg class="qh-orbit__wave" style="right:2px;" width="14" height="20" viewBox="0 0 14 20" fill="none"><path d="M3 3Q10 10 3 17M7 6.5Q10.5 10 7 13.5" stroke="#7B9B63" stroke-width="1.5" stroke-linecap="round"/></svg>
            <view class="qh-orbit__dot"/>
          </view>
          <view class="qh-devicerow">
            <text class="qh-devicename">声学驱鸟器 01</text>
            <view class="qh-pill"><view class="qh-pill__dot"/><text class="qh-pill__text">{{ offline ? '离线' : '在线' }}</text></view>
          </view>
          <text class="qh-devicecode">东区果园 · ACOUSTIC 01</text>
          <view v-if="selectedAlarm" class="qh-linkstrip">
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M5.5 7.5a3 3 0 004.2 0l1.8-1.8a3 3 0 00-4.2-4.2L6.2 2.6M7.5 5.5a3 3 0 00-4.2 0L1.5 7.3a3 3 0 004.2 4.2l1.1-1.1" stroke="#96682B" stroke-width="1.4" stroke-linecap="round"/></svg>
            <text class="qh-linkstrip__text">关联告警 {{ selectedAlarm }}</text>
            <text class="qh-linkstrip__cancel" @click="selectedAlarm = null">取消关联</text>
          </view>
        </view>

        <view class="qh-durcard">
          <view class="qh-durcard__top"><text class="qh-durcard__label">单次执行时长</text><text class="qh-durcard__note">定时结束 · 不连续运行</text></view>
          <view class="qh-duropts">
            <view v-for="d in [3,5,8]" :key="d" class="qh-duropt" :class="{ 'is-selected': duration === d }" @click="duration = d">{{ d }} 秒</view>
          </view>
        </view>

        <view v-if="store.active" class="qh-card">
          <view class="qh-resultcard" style="padding:0;background:transparent">
            <view class="qh-resultcard__info grow"><text class="qh-resultcard__title">{{ names(store.active.status) }}</text><text class="qh-resultcard__desc">{{ store.active.message }}</text></view>
            <text class="qh-paramrow__value" style="font-family:var(--font-num)">{{ remaining }}s</text>
          </view>
          <view class="qh-progress" style="margin-top:10px"><view class="qh-progress__bar" :style="{ width: (store.active.status === 'pending' ? 0 : Math.min(100, (1 - remaining / store.active.duration) * 100)) + '%' }"/></view>
          <button class="qh-btn qh-btn--ghost-danger" style="width:100%;margin-top:10px;border:1px solid var(--line-strong);min-height:40px;font-size:var(--text-md);color:var(--danger-fg)" :disabled="store.busy" @click="run(() => store.mutate('/commands/' + store.active!.id + '/stop'))">停止本次执行</button>
        </view>

        <view v-else-if="s?.commands[0]" class="qh-resultcard" style="cursor:pointer" @click="detailId = s.commands[0].id; modal = 'mLog'">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="7.5" stroke="#56753F" stroke-width="1.5"/><path d="M5.8 9.2l2.2 2.2 4.2-4.6" stroke="#56753F" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <view class="qh-resultcard__info"><text class="qh-resultcard__title">最近一次执行 · {{ names(s.commands[0].status) }}</text><text class="qh-resultcard__desc">{{ s.commands[0].message }}</text></view>
        </view>

        <button class="qh-btn qh-btn--primary" :disabled="store.busy || offline || !!store.active" @click="modal = 'mConfirm'">
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><path d="M2 5.5v4h2.5L8 12.5v-10L4.5 5.5H2z" fill="#F5F7EC"/><path d="M10.5 5a3.5 3.5 0 010 5M12.5 3a6.5 6.5 0 010 9" stroke="#F5F7EC" stroke-width="1.4" stroke-linecap="round"/></svg>{{ offline ? '设备离线，无法执行' : '执行一次驱离' }}
        </button>

        <text class="qh-note">本设备是模拟执行器，不会控制真实硬件</text>
        <view class="qh-shortcut" @click="settings">
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><rect x="1" y="1" width="4.6" height="4.6" rx="1" stroke="#8A917F" stroke-width="1.3"/><rect x="7.4" y="1" width="4.6" height="4.6" rx="1" stroke="#8A917F" stroke-width="1.3"/><rect x="1" y="7.4" width="4.6" height="4.6" rx="1" stroke="#8A917F" stroke-width="1.3"/><rect x="7.4" y="7.4" width="4.6" height="4.6" rx="1" stroke="#8A917F" stroke-width="1.3"/></svg>
          <text>切换离线 / 超时演示场景</text>
        </view>
      </view>
    </view>

    <!-- ======================= 记录页 ======================= -->
    <view class="page" :class="{ 'is-current': store.token && page === 'records' }">
      <view class="statusbar">
        <text class="time">9:41</text>
        <view class="icons">
          <svg width="18" height="12" viewBox="0 0 18 12" fill="none"><rect y="7" width="3" height="5" rx="1" fill="#232B1D"/><rect x="5" y="5" width="3" height="7" rx="1" fill="#232B1D"/><rect x="10" y="2.5" width="3" height="9.5" rx="1" fill="#232B1D"/><rect x="15" width="3" height="12" rx="1" fill="#232B1D"/></svg>
          <svg width="17" height="12" viewBox="0 0 17 12" fill="none"><path d="M1 4a11 11 0 0115 0M3.7 6.8a7 7 0 019.6 0M6.4 9.4a3.2 3.2 0 014.2 0" stroke="#232B1D" stroke-width="1.6" stroke-linecap="round"/><circle cx="8.5" cy="10.5" r="1.2" fill="#232B1D"/></svg>
          <svg width="25" height="12" viewBox="0 0 25 12" fill="none"><rect x=".5" y=".5" width="21" height="11" rx="3" stroke="#232B1D" stroke-opacity=".4"/><rect x="2" y="2" width="15" height="8" rx="1.5" fill="#232B1D"/></svg>
        </view>
      </view>
      <view class="page__content">
        <view class="qh-header__brand">
          <text class="qh-page-title">检测档案</text>
          <text class="qh-page-subtitle">按视频回看，按鸟类查找</text>
        </view>
        <view class="qh-seg">
          <view class="qh-seg__item" :class="{ 'is-active': recordMode === 'videos' }" @click="recordMode = 'videos'">视频与鸟类</view>
          <view class="qh-seg__item" :class="{ 'is-active': recordMode === 'actions' }" @click="recordMode = 'actions'">处理操作记录</view>
        </view>
        <VideoLibrary v-if="recordMode === 'videos'" :key="archiveNonce" :initial-task="archiveTask" :initial-time="archiveTime" />
        <template v-else>
          <view class="qh-stats">
            <view class="qh-stat"><text class="qh-stat__num">{{ s?.counts.total || 0 }}</text><text class="qh-stat__label">检测事件</text></view>
            <view class="qh-stat"><text class="qh-stat__num">{{ s?.counts.completed || 0 }}</text><text class="qh-stat__label">模拟执行完成</text></view>
          </view>
          <view class="qh-seg">
            <view v-for="it in [{id:'all',name:'全部记录'},{id:'detection',name:'检测事件'},{id:'actions',name:'处理操作'}]" :key="it.id" class="qh-seg__item" :class="{ 'is-active': recordFilter === it.id }" @click="recordFilter = it.id">{{ it.name }}</view>
          </view>
          <view v-for="ev in events" :key="ev.id" class="qh-card" style="cursor:pointer" @click="run(() => inspectEvent(ev))">
            <text class="qh-tl__title">{{ ev.message }}</text>
            <text class="qh-tl__msg">{{ time(ev.at) }} · {{ ev.ref_id }}</text>
          </view>
          <view v-if="!events.length" style="padding:40px 0;text-align:center"><text class="qh-note">开始巡护，留下第一条记录</text></view>
          <button v-if="!historyEnd && ((s?.events.length || 0) >= 100 || older.length)" class="qh-btn qh-btn--secondary qh-btn--sm" style="width:100%" :disabled="store.busy" @click="run(loadHistory)">加载更早记录</button>
        </template>
      </view>
    </view>

    <!-- ======================= 底部导航 ======================= -->
    <view v-if="store.token" class="qh-tabbar">
      <view class="qh-tabbar__pill">
        <button class="qh-tab" :class="{ 'is-active': page === 'monitor' }" @click="go('monitor')">
          <svg width="19" height="19" viewBox="0 0 19 19" fill="none"><path d="M1.5 9.5C3.5 5.5 6.3 3.5 9.5 3.5s6 2 8 6c-2 4-4.8 6-8 6s-6-2-8-6z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><circle cx="9.5" cy="9.5" r="2.5" fill="currentColor"/></svg>
          <text>监控</text>
        </button>
        <button class="qh-tab" :class="{ 'is-active': page === 'alarms' }" @click="go('alarms')">
          <svg width="19" height="19" viewBox="0 0 19 19" fill="none"><path d="M9.5 2.5a5 5 0 015 5v3l1.5 2.5h-13L4.5 10.5v-3a5 5 0 015-5z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M7.8 15.5a1.8 1.8 0 003.4 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
          <text class="qh-tab__labelrow">告警<text v-if="s?.counts.pending" class="qh-tab__badge">{{ s.counts.pending }}</text></text>
        </button>
        <button class="qh-tab" :class="{ 'is-active': page === 'control' }" @click="go('control')">
          <svg width="19" height="19" viewBox="0 0 19 19" fill="none"><path d="M9.5 2v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M5.2 4.8a7 7 0 108.6 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
          <text>控制</text>
        </button>
        <button class="qh-tab" :class="{ 'is-active': page === 'records' }" @click="go('records')">
          <svg width="19" height="19" viewBox="0 0 19 19" fill="none"><rect x="2.5" y="3" width="14" height="4" rx="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M4 7v7a2 2 0 002 2h7a2 2 0 002-2V7M7.5 10.5h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
          <text>记录</text>
        </button>
      </view>
    </view>

    <!-- ======================= 弹窗：设置 ======================= -->
    <view v-if="modal === 'mSet'" class="qh-mask qh-mask--bottom is-open" @click.self="modal = ''">
      <view class="qh-sheet">
        <view class="qh-sheet__grab"/>
        <view class="qh-sheet__titlerow"><text class="qh-sheet__title">设置</text><view class="qh-iconbtn--sm" @click="modal = ''"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2l-8 8" stroke="#6D7F6C" stroke-width="1.5" stroke-linecap="round"/></svg></view></view>
        <text style="font-size:var(--text-base);font-weight:500;color:var(--ink-900);">场景切换</text>
        <view v-for="opt in [{id:'normal',name:'正常执行',desc:'识别到鸟类后人工确认驱离'},{id:'offline',name:'设备离线',desc:'演示设备不在线时的界面与提示'},{id:'timeout',name:'执行超时',desc:'演示指令无响应时的状态与恢复'}]" :key="opt.id" class="qh-radio" :class="{ 'is-selected': preferences.scenario === opt.id }" @click="preferences.scenario = opt.id as Preferences['scenario']">
          <view class="qh-radio__circle"><view class="qh-radio__dot"/></view>
          <view class="qh-radio__info"><text class="qh-radio__name">{{ opt.name }}</text><text class="qh-radio__desc">{{ opt.desc }}</text></view>
        </view>
        <view class="qh-paramrow"><view class="qh-paramrow__top"><text class="qh-paramrow__name">置信度阈值</text><text class="qh-paramrow__value">{{ preferences.confidence.toFixed(2) }}</text></view><view class="qh-slider"><view class="qh-slider__track"/><view class="qh-slider__fill" :style="{ width: ((preferences.confidence - 0.1) / 0.85 * 100) + '%' }"/><view class="qh-slider__knob" :style="{ left: 'calc(' + ((preferences.confidence - 0.1) / 0.85 * 100) + '% - 9px)' }"/></view></view>
        <view class="qh-paramrow"><view class="qh-paramrow__top"><text class="qh-paramrow__name">连续检出帧数</text><text class="qh-paramrow__value">{{ preferences.consecutive }} 帧</text></view><view class="qh-slider"><view class="qh-slider__track"/><view class="qh-slider__fill" :style="{ width: ((preferences.consecutive - 1) / 9 * 100) + '%' }"/><view class="qh-slider__knob" :style="{ left: 'calc(' + ((preferences.consecutive - 1) / 9 * 100) + '% - 9px)' }"/></view></view>
        <view class="qh-paramrow"><view class="qh-paramrow__top"><text class="qh-paramrow__name">事件合并间隔</text><text class="qh-paramrow__value">{{ preferences.cooldown }} 秒</text></view><view class="qh-slider"><view class="qh-slider__track"/><view class="qh-slider__fill" :style="{ width: ((preferences.cooldown - 1) / 299 * 100) + '%' }"/><view class="qh-slider__knob" :style="{ left: 'calc(' + ((preferences.cooldown - 1) / 299 * 100) + '% - 9px)' }"/></view></view>
        <button class="qh-btn qh-btn--primary" :disabled="store.busy || !!store.active" @click="run(async() => { await store.mutate('/settings','PUT',preferences); modal=''; notify('设置已保存') })">保存设置</button>
        <view class="qh-logoutrow"><text style="color:var(--danger-fg)" @click="run(() => store.logout())">退出登录</text><text style="color:var(--brand-500)" @click="run(() => store.logout())">更换服务</text></view>
        <text class="qh-svcinfo">服务 {{ store.server }} · 视频 HLS · 推理 {{ s?.monitor.device || 'cpu' }} · {{ s?.monitor.sample_fps || 2 }} 帧/秒抽样</text>
      </view>
    </view>

    <!-- ======================= 弹窗：告警详情 ======================= -->
    <view v-if="modal === 'mAlarm' && alarm" class="qh-mask qh-mask--center is-open" @click.self="modal = ''">
      <view class="qh-dialog">
        <image class="qh-detailimg" :src="store.media('captures/' + alarm.snapshot)" mode="aspectFill"/>
        <view class="qh-dialog__titlerow"><text class="qh-dialog__title">{{ alarm.species }} · {{ alarm.count }} 只</text><text :class="alarmClass(alarm.status)">{{ names(alarm.status) }}</text></view>
        <view class="qh-infogrid">
          <view class="qh-infogrid__row">
            <view class="qh-infocell"><text class="qh-infocell__label">置信度</text><text class="qh-infocell__value">{{ (alarm.confidence * 100).toFixed(0) }}%</text></view>
            <view class="qh-infocell"><text class="qh-infocell__label">发现时间</text><text class="qh-infocell__value">{{ clock(alarm.at) }}</text></view>
          </view>
          <view class="qh-infogrid__row">
            <view class="qh-infocell"><text class="qh-infocell__label">录像位置</text><text class="qh-infocell__value">{{ alarm.video_time.toFixed(1) }}s</text></view>
            <view class="qh-infocell"><text class="qh-infocell__label">监控点</text><text class="qh-infocell__value">东区·01</text></view>
          </view>
        </view>
        <view class="qh-btnrow">
          <button class="qh-btn qh-btn--half qh-btn--ghost-danger" :disabled="store.busy" @click="alarm.status === 'new' ? run(async() => { await store.mutate('/alarms/' + alarm!.id + '/ignore'); modal = '' }) : replayAlarm(alarm)">{{ alarm.status === 'new' ? '忽略' : '回看视频' }}</button>
          <button class="qh-btn qh-btn--half qh-btn--primary" :disabled="store.busy" @click="alarm.status === 'new' ? handle() : modal = ''">{{ alarm.status === 'new' ? '确认驱离' : '关闭' }}</button>
        </view>
      </view>
    </view>

    <!-- ======================= 弹窗：确认执行 ======================= -->
    <view v-if="modal === 'mConfirm'" class="qh-mask qh-mask--center is-open" @click.self="modal = ''">
      <view class="qh-dialog">
        <view style="width:44px;height:44px;border-radius:50%;background:var(--warn-bg);display:flex;align-items:center;justify-content:center;">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M3 8v4h3l4 3.5v-11L6 8H3z" fill="#96682B"/><path d="M13 7a4.5 4.5 0 010 6M15.5 5a8 8 0 010 10" stroke="#96682B" stroke-width="1.5" stroke-linecap="round"/></svg>
        </view>
        <text class="qh-dialog__title">确认执行驱离？</text>
        <text class="qh-dialog__desc">设备将以声学方式驱离鸟类，定时结束后自动停止。</text>
        <view class="qh-confinfo">
          <view class="qh-confinfo__row"><text class="qh-confinfo__label">执行时长</text><text class="qh-confinfo__value">{{ duration }} 秒 · 定时结束</text></view>
          <view class="qh-confinfo__row"><text class="qh-confinfo__label">关联事件</text><text class="qh-confinfo__value">{{ selectedAlarm || '手动操作' }}</text></view>
          <view class="qh-confinfo__row"><text class="qh-confinfo__label">执行设备</text><text class="qh-confinfo__value">声学驱鸟器 01 · {{ offline ? '离线' : '在线' }}</text></view>
        </view>
        <view class="qh-btnrow">
          <button class="qh-btn qh-btn--half qh-btn--ghost-danger" @click="modal = ''">取消</button>
          <button class="qh-btn qh-btn--half qh-btn--primary" :disabled="store.busy" @click="run(execute)">{{ store.busy ? '正在提交…' : '确认执行' }}</button>
        </view>
        <text class="qh-confnote">模拟执行器 · 不会控制真实硬件</text>
      </view>
    </view>

    <!-- ======================= 弹窗：操作记录 ======================= -->
    <view v-if="modal === 'mLog' && command" class="qh-mask qh-mask--bottom is-open" @click.self="modal = ''">
      <view class="qh-sheet">
        <view class="qh-sheet__grab"/>
        <view class="qh-sheet__titlerow">
          <view><text class="qh-sheet__title">操作记录</text><text style="display:block;font-size:var(--text-xs);color:var(--ink-400);margin-top:3px;">{{ command.id }}<text v-if="command.alarm_id"> · {{ command.alarm_id }}</text></text></view>
          <view class="qh-iconbtn--sm" @click="modal = ''"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2l-8 8" stroke="#6D7F6C" stroke-width="1.5" stroke-linecap="round"/></svg></view>
        </view>
        <view class="qh-tl">
          <view class="qh-tl__item"><view class="qh-tl__dot qh-tl__dot--confirm"/><view class="qh-tl__info"><view class="qh-tl__head"><text class="qh-tl__title">人工确认</text><text class="qh-tl__time">{{ time(command.at) }}</text></view><text class="qh-tl__msg">确认了下发一次 {{ command.duration }} 秒驱离操作</text></view></view>
          <view class="qh-tl__item"><view class="qh-tl__dot" :class="command.started_at ? 'qh-tl__dot--running' : 'qh-tl__dot--confirm'"/><view class="qh-tl__info"><view class="qh-tl__head"><text class="qh-tl__title">{{ command.started_at ? '开始执行' : '尚未执行' }}</text><text v-if="command.started_at" class="qh-tl__time">{{ time(command.started_at) }}</text></view><text class="qh-tl__msg">声学驱鸟器 01 · 时长 {{ command.duration }} 秒 · 定时结束</text></view></view>
          <view class="qh-tl__item"><view class="qh-tl__dot" :class="command.status === 'completed' ? 'qh-tl__dot--done' : command.status === 'failed' ? 'qh-tl__dot--confirm' : 'qh-tl__dot--running'"/><view class="qh-tl__info"><view class="qh-tl__head"><text class="qh-tl__title">{{ names(command.status) }}</text><text v-if="command.ended_at" class="qh-tl__time">{{ time(command.ended_at) }}</text></view><text class="qh-tl__msg">{{ command.message }}</text></view></view>
        </view>
        <text class="qh-svcinfo">{{ command.status === 'completed' ? '此记录只证明模拟指令完成，不代表真实驱鸟成功' : '未完成的操作不会将告警标记为已处理' }}</text>
      </view>
    </view>
  </view>
</template>
