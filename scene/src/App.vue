<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { createOrchardScene } from './lib/renderer.js'
import { state, connect, disconnect, resume, clearSession, defaultServer } from './lib/data.js'

/* ---------- 场景 ---------- */
const canvas = ref(null)
const ready = ref(false)
const loadProgress = ref(0)

/* ---------- 登录 ---------- */
const serverInput = ref('')
const username = ref('orchard')
const password = ref('')
const needLogin = computed(() => !state.token)
const loginError = ref('')
const loggingIn = ref(false)
const sceneError = ref('')  // WebGL 不可用或场景初始化失败

let handle = null

/* ---------- 状态文案 ---------- */
const STATUS_TEXT = {
  idle: '未开始',
  starting: '加载模型',
  running: '正在监测',
  stopping: '正在停止',
  stopped: '已停止',
  ended: '检测完成',
  interrupted: '服务中断',
  error: '检测异常',
}
const monitorLabel = computed(() => STATUS_TEXT[state.monitorStatus] || state.monitorStatus)

const badgeClass = computed(() => {
  const s = state.monitorStatus
  if (s === 'running' || s === 'starting') return 'hud-badge is-live'
  if (s === 'ended') return 'hud-badge is-ended'
  if (s === 'error' || s === 'interrupted') return 'hud-badge is-warn'
  return 'hud-badge'
})

const offline = computed(() => state.scenario === 'offline')

/** 最近 6 条告警，供右侧面板展示 */
const recentAlarms = computed(() => state.alarms.slice(0, 3))

const executing = computed(() => !!state.activeCommand)
/* 驱离完成瞬间:按钮短暂变绿提示「鸟群散去」 */
/* 声波驱离音效:WebAudio 脉冲警笛;静音开关持久化;AudioContext 在用户手势后创建 */
const soundEnabled = ref(localStorage.getItem('bird-scene-sound') === 'on')
let audioCtx = null, audioOsc = null, audioLfo = null, audioGain = null, audioLfoGain = null
function startRepelSound() {
  if (!soundEnabled.value || audioOsc) return
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)()
    if (audioCtx.state === 'suspended') audioCtx.resume()
    audioOsc = audioCtx.createOscillator()
    audioGain = audioCtx.createGain()
    audioOsc.type = 'sawtooth'
    audioOsc.frequency.value = 640
    audioLfo = audioCtx.createOscillator()
    audioLfo.frequency.value = 2.4
    audioLfoGain = audioCtx.createGain()
    audioLfoGain.gain.value = 340
    audioLfo.connect(audioLfoGain)
    audioLfoGain.connect(audioOsc.frequency)
    audioGain.gain.value = 0.03
    audioOsc.connect(audioGain)
    audioGain.connect(audioCtx.destination)
    audioOsc.start(); audioLfo.start()
  } catch { stopRepelSound() }
}
function stopRepelSound() {
  try { audioOsc?.stop(); audioLfo?.stop(); audioGain?.disconnect(); audioLfoGain?.disconnect() } catch { /* already stopped */ }
  audioOsc = audioLfo = null
}
function toggleSound() {
  soundEnabled.value = !soundEnabled.value
  localStorage.setItem('bird-scene-sound', soundEnabled.value ? 'on' : 'off')
  if (!soundEnabled.value) stopRepelSound()
}
const repelDone = ref(false)
let repelDoneTimer = null
/* 果农流程横向步骤条:phase → 当前步索引 */
const crewStepIndex = computed(() => ({ home: -1, alert: 0, working: 1, positioned: 1, actuating: 2, waiting: 3, returning: 3 }[crewPhase.value] ?? -1))
/* 最近检测 → 3D 场景定位(bbox 映射与 renderer 同源);再次点击返回全景 */
const focusTarget = ref('')
const focusedAlarm = computed(() => state.alarms.find(a => a.id === focusTarget.value))
const captureFailed = ref(false)
const focusedCapture = computed(() => {
  const name = focusedAlarm.value?.snapshot
  return name && state.mediaTicket
    ? `${state.server || defaultServer()}/api/captures/${encodeURIComponent(name)}?ticket=${encodeURIComponent(state.mediaTicket)}`
    : ''
})
watch(focusedCapture, () => { captureFailed.value = false })
const detectedCount = computed(() => state.detections.length)
function focusAlarm(a) {
  if (!handle) return
  if (focusTarget.value === a.id) {
    handle.resetView()
    focusTarget.value = ''
    return
  }
  let bbox = null
  try { bbox = typeof a.bbox === 'string' ? JSON.parse(a.bbox) : (a.bbox || null) } catch { bbox = null }
  if (!handle.focusDetection || !bbox) return
  handle.focusDetection(bbox, a.species)
  focusTarget.value = a.id
}
function hasBbox(a) {
  let bbox = null
  try { bbox = typeof a.bbox === 'string' ? JSON.parse(a.bbox) : (a.bbox || null) } catch { return false }
  return Array.isArray(bbox) && bbox.length === 4
}

const responseMode = ref(localStorage.getItem('bird-scene-response-mode') === 'auto' ? 'auto' : 'manual')
const selectedRepelMode = ref('both')
const effectiveRepelMode = computed(() => responseMode.value === 'auto' ? 'both' : selectedRepelMode.value)
watch(executing, (now) => { now ? startRepelSound() : stopRepelSound() })
const crewPhase = ref('patrol')
const crewExpanded = ref(false)
const daylightExpanded = ref(false)
const controlCollapsed = ref(typeof window !== 'undefined' && window.innerWidth <= 640)
const infoCollapsed = ref(typeof window !== 'undefined' && window.innerWidth <= 640)
const crewTasks = computed(() => [
  { key: 'inspect', title: '检查果树', detail: '巡看果树与鸟害位置', enabled: true },
  { key: 'infrared', title: '开启红外驱鸟器', detail: '对准目标鸟类发射红色光束', enabled: effectiveRepelMode.value !== 'acoustic' },
  { key: 'acoustic', title: '开启声波驱鸟器', detail: '启动声波模拟驱离', enabled: effectiveRepelMode.value !== 'infrared' },
].map((task, index) => ({
  ...task,
  status: crewPhase.value === 'patrol' ? `巡逻中 · ${['果园', '麦田', '菜地'][index]}` + (responseMode.value === 'manual' ? '（手动模式）' : '')
    : crewPhase.value === 'alert' ? '发现鸟类 · 正在集结'
      : crewPhase.value === 'working' ? task.enabled ? '前往作业点' : '本次未启用'
        : crewPhase.value === 'positioned' ? task.enabled ? '已抵达 · 等待启动' : '本次未启用'
          : crewPhase.value === 'actuating' ? task.enabled ? '正在执行' : '本次未启用'
            : crewPhase.value === 'waiting' ? task.enabled ? '已执行 · 等待复核' : '本次未启用'
              : crewPhase.value === 'returning' ? '任务完成 · 返回巡逻区' : '待命',
})))
const crewPhaseLabel = computed(() => {
  if (crewPhase.value === 'patrol' && responseMode.value === 'manual') return '手动控制 · 果农分区巡逻'
  return ({ patrol: '三分区日常巡逻', alert: '发现目标 · 集结中', working: '前往设备', positioned: '已抵达设备', actuating: '设备执行中', waiting: '等待复核', returning: '返回巡逻区' }[crewPhase.value] || '待命')
})

/** 当前指令的驱离方式：acoustic / infrared / both */
const repelMode = computed(() => state.activeCommand?.mode || 'both')
const acousticDesc = computed(() => {
  if (!executing.value) return '模拟设备 · 待命'
  if (repelMode.value === 'infrared') return '待命 · 红外执行中'
  return '正在执行声波驱离'
})
const irDesc = computed(() => {
  if (!executing.value) return '红外脉冲 · 待命'
  if (repelMode.value === 'infrared') return '正在执行红外驱离'
  if (repelMode.value === 'acoustic') return '待命 · 声波执行中'
  return '红外脉冲 · 与声学联动'
})

/** 待驱离鸟数（由 3D 场景回报） */
const birdCount = ref(0)
/** 本次演示的驱离次数 */
const repelCount = ref(0)
/** 上一次已结算的驱离指令 id，避免重复触发 */
const settledCommandIds = new Set()

/**
 * 监听驱离指令完成：每次成功驱离驱散一部分鸟。
 * 后端的指令状态流转：pending -> running -> completed
 */
watch(
  () => state.commands,
  (cmds) => {
    if (!Array.isArray(cmds)) return
    for (const c of cmds) {
      if (!['completed', 'failed', 'unknown', 'cancelled'].includes(c.status)) continue
      if (settledCommandIds.has(c.id)) continue
      // 只结算最近 30 秒内的指令，避免加载历史数据时批量触发
      if (c.ended_at && Date.now() / 1000 - c.ended_at > 30) {
        settledCommandIds.add(c.id)
        continue
      }
      settledCommandIds.add(c.id)
      if (['failed', 'unknown', 'cancelled'].includes(c.status)) {
        repelDone.value = false
        repelFail.value = true
        flash(c.status === 'cancelled' ? '指令已取消，未确认驱离效果' : '指令未成功，请检查设备后重试')
        if (c.automatic) {
          crewPhase.value = 'positioned'
          flash('驱离未完成，果农仍在设备旁待命')
        }
        break
      }
      repelDone.value = true
      clearTimeout(repelDoneTimer)
      repelDoneTimer = setTimeout(() => { repelDone.value = false }, 4000)
      if (handle) {
        const before = handle.occupantCount()
        const left = handle.disperse()
        birdCount.value = left
        repelCount.value += 1
        const autoCommand = !!c.automatic
        if (left === 0) {
          repelFail.value = false
          flash('模拟鸟群已散去 · 实际效果请复核监控画面')
          crewPhase.value = autoCommand ? 'returning' : 'patrol'
          // returning 的实际行走时长由路点图距离决定,renderer 走完经 onCrewReturned 回到 patrol
        } else if (left === before) {
          // 本次声波没有驱走任何一只（拟真：单只时有可能抵抗）
          repelFail.value = true
          flash('模拟鸟群仍停留 · 请复核监控画面')
          crewPhase.value = autoCommand ? 'positioned' : 'patrol'
        } else {
          repelFail.value = false
          flash(`模拟驱离后剩余 ${left} 只 · 实际效果待复核`)
          crewPhase.value = autoCommand ? 'positioned' : 'patrol'
        }
        if (left > 0 && autoCommand && responseMode.value === 'auto') scheduleAutomaticRetry()
      } else {
        flash('指令执行完成 · 实际效果待复核')
      }
      break
    }
  },
  { deep: false },
)

/** 驱离操作反馈，2.5 秒后自动消失 */
const repelMsg = ref('')
const repelFail = ref(false)   // 本次驱离未驱走任何鸟
let repelMsgTimer = 0
let crewReturnTimer = 0
let autoResponseTimer = 0
let lastDetectionSignature = ''
let monitorFrameBaseline = 0
function flash(msg) {
  repelMsg.value = msg
  clearTimeout(repelMsgTimer)
  repelMsgTimer = setTimeout(() => { repelMsg.value = '' }, 2500)
}

const timeText = (at) => {
  if (!at) return ''
  const d = new Date(at * 1000)
  return d.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' })
}

/* ---------- 把业务状态喂给 3D ---------- */
function pushStateToScene() {
  if (!handle) return
  // 按物种汇总一张抓拍图 + 该帧 bbox（后端成对保存），供 3D 鸟做真实照片贴图
  const snapshots = {}
  for (const a of state.alarms) {
    if (a.snapshot && !snapshots[a.species]) {
      let bbox = null
      try { bbox = typeof a.bbox === 'string' ? JSON.parse(a.bbox) : (a.bbox || null) } catch { bbox = null }
      snapshots[a.species] = { name: a.snapshot, bbox }
    }
  }
  handle.setState({
    running: state.monitorStatus === 'running' || state.monitorStatus === 'starting',
    detections: state.detections,
    alarms: state.alarms.filter((a) => a.status === 'new'),
    executing: executing.value,
    offline: offline.value,
    // 当前帧的录像时间戳，用于告警精确关联
    detTime: state.snapshot?.monitor?.frame?.video_time ?? 0,
    // 驱离方式：声学 / 红外 / 双模（3D 场景只点亮对应设备的动效）
    repelMode: (state.activeCommand?.mode) || effectiveRepelMode.value,
    crewPhase: crewPhase.value,
    snapshots,
    server: state.server || defaultServer(),
    // 抓拍接口用媒体票据鉴权（?ticket=），不是 Bearer token
    ticket: state.mediaTicket,
  })
  // 同步待驱离鸟数到 HUD
  birdCount.value = handle.occupantCount()
}

// 重新开始检测时清空上一轮的居留鸟群
watch(
  () => state.monitorStatus,
  (now, before) => {
    const starting = now === 'running' || now === 'starting'
    const wasIdle = before === 'ended' || before === 'stopped' || before === 'idle'
    if (starting && wasIdle && handle) {
      handle.clearOccupants()
      birdCount.value = 0
      repelCount.value = 0
      crewPhase.value = 'patrol'
      lastDetectionSignature = ''
      monitorFrameBaseline = state.snapshot?.monitor?.frame?.frame_id || 0
      clearTimeout(autoResponseTimer)
      clearTimeout(crewReturnTimer)
    }
  },
  { flush: 'post' },
)

function detectionSignature(detections) {
  return (detections || [])
    .map((d) => `${d.species || 'unknown'}:${Math.round((d.confidence || 0) * 100)}`)
    .sort()
    .join('|')
}

function scheduleAutomaticRetry(delay = 400) {
  clearTimeout(autoResponseTimer)
  autoResponseTimer = setTimeout(() => {
    if (responseMode.value !== 'auto' || crewPhase.value !== 'positioned' || birdCount.value < 1 || executing.value) return
    repel('both', true)
  }, delay)
}

function onCrewAlertReady() {
  if (responseMode.value === 'auto' && crewPhase.value === 'alert' && birdCount.value > 0) crewPhase.value = 'working'
}

function onCrewArrived() {
  if (responseMode.value !== 'auto' || crewPhase.value !== 'working' || birdCount.value < 1 || executing.value) return
  crewPhase.value = 'positioned'
  scheduleAutomaticRetry(350)
}

watch(
  () => [state.monitorStatus, state.snapshot?.monitor?.frame?.frame_id || 0, detectionSignature(state.detections)],
  ([status, frameId, signature]) => {
    if (!signature) {
      if (crewPhase.value === 'patrol') lastDetectionSignature = ''
      return
    }
    if (frameId && frameId === monitorFrameBaseline) return
    if (!['running', 'ended'].includes(status) || signature === lastDetectionSignature) return
    lastDetectionSignature = signature
    if (responseMode.value !== 'auto') return
    if (crewPhase.value !== 'patrol' || !handle?.occupantCount()) return
    crewPhase.value = 'alert'
  },
  { flush: 'post' },
)

watch(
  () => [
    state.monitorStatus,
    state.detections.length,
    state.alarms.length,
    state.activeCommand && state.activeCommand.id,
    state.scenario,
    state.snapshot?.monitor?.frame?.frame_id,  // 帧推进时也触发更新
    state.snapshot?.monitor?.frame?.video_time,
    crewPhase.value,
    effectiveRepelMode.value,
  ],
  pushStateToScene,
  { deep: false },
)

/* ---------- 生命周期 ---------- */
onMounted(() => {
  loadProgress.value = 30

  // WebGL 可用性检测
  const testCanvas = document.createElement('canvas')
  const gl = testCanvas.getContext('webgl2') || testCanvas.getContext('webgl')
  if (!gl) {
    loadProgress.value = 100
    ready.value = true
    sceneError.value = '你的浏览器不支持 WebGL，无法渲染 3D 场景。请尝试更新浏览器或启用硬件加速。'
    return
  }

  try {
    handle = createOrchardScene(canvas.value, {
      onReady: () => {
        loadProgress.value = 100
        ready.value = true
      },
      onAutoRotateChange: (on) => { autoRotate.value = on },
      onCrewAlertReady,
      onCrewArrived,
      onCrewReturned: () => { crewPhase.value = 'patrol' },
    })
    // 供自动化验证读取内部状态
    window.__sceneHandle = handle
  } catch (err) {
    loadProgress.value = 100
    ready.value = true
    sceneError.value = '3D 场景初始化失败：' + (err.message || err)
    return
  }

  serverInput.value = defaultServer() || window.location.origin
  // 会话恢复：优先 3D 页自己的凭据；否则复用 H5 端的登录态（一次登录，两端联动）
  const savedToken = localStorage.getItem('bird-scene-token') || localStorage.getItem('bird-session')
  const savedServer = localStorage.getItem('bird-scene-server') || localStorage.getItem('bird-server')
  if (savedToken && savedServer) {
    state.token = savedToken
    state.server = savedServer
    resume(savedToken, savedServer)
    // 用已有 token 拉状态
    fetch(`${savedServer}/api/state`, { headers: { Authorization: 'Bearer ' + savedToken } })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) {
          state.snapshot = data
          state.monitorStatus = data.monitor?.status || 'idle'
          state.detections = data.monitor?.frame?.detections || []
          state.alarms = data.alarms || []
          state.commands = data.commands || []
          state.counts = data.counts || state.counts
          state.scenario = data.settings?.scenario || 'normal'
          state.activeCommand = state.commands.find((c) => c.status === 'pending' || c.status === 'running') || null
          pushStateToScene()
        }
      })
      .catch(() => {})
  }
})

onBeforeUnmount(() => {
  clearTimeout(autoResponseTimer)
  clearTimeout(crewReturnTimer)
  clearTimeout(repelMsgTimer)
  clearTimeout(repelDoneTimer)
  if (handle) handle.dispose()
  disconnect()
})

function togglePanel(panel) {
  const target = panel === 'control' ? controlCollapsed : infoCollapsed
  target.value = !target.value
  if (!target.value && window.innerWidth <= 640) {
    if (panel === 'control') infoCollapsed.value = true
    else controlCollapsed.value = true
  }
}

/* ---------- 登录动作 ---------- */
async function doLogin() {
  if (loggingIn.value || !password.value) return
  loggingIn.value = true
  loginError.value = ''
  const server = serverInput.value.trim() || defaultServer()
  state.server = server.replace(/\/$/, '')
  const ok = await connect(username.value.trim(), password.value)
  loggingIn.value = false
  if (ok) {
    password.value = ''
    localStorage.setItem('bird-scene-token', state.token)
    localStorage.setItem('bird-scene-server', state.server)
    pushStateToScene()
  } else {
    loginError.value = state.error || '登录失败'
  }
}

function resetView() {
  focusTarget.value = ''
  if (handle) handle.resetView()
}

/* ---------- 声波驱离 ---------- */
const repelling = ref(false)

/** 在 3D 场景里发起一次驱离：调用后端 /api/commands，完成后由 watch 结算 */
async function repel(mode = selectedRepelMode.value, automatic = false) {
  if (repelling.value || executing.value) return
  if (!state.token) return
  repelling.value = true
  try {
    // 关联第一条待处理告警（如果有）
    const alarm = state.alarms.find((a) => a.status === 'new')
    const requestId = 'ui' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
    const res = await fetch(`${state.server}/api/commands`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + state.token,
      },
      body: JSON.stringify({
        request_id: requestId,
        alarm_id: alarm ? alarm.id : null,
        duration: 3,
        mode,
        automatic,
      }),
    })
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      state.error = detail.detail || '驱离指令下发失败'
      flash(state.error)
    } else {
      if (automatic) crewPhase.value = 'actuating'
      flash(automatic ? '果农已触达设备，自动驱离启动' : '手动驱离指令已下发')
    }
    // 指令完成后会由 watch(state.commands) 触发 disperse()
  } catch (err) {
    state.error = '驱离请求失败：' + (err.message || err)
    flash(state.error)
  } finally {
    repelling.value = false
  }
}

function setResponseMode(mode) {
  if (executing.value || repelling.value) return
  responseMode.value = mode
  localStorage.setItem('bird-scene-response-mode', mode)
  clearTimeout(autoResponseTimer)
  if (mode === 'auto' && crewPhase.value === 'patrol' && (handle?.occupantCount() || 0) > 0) {
    birdCount.value = handle.occupantCount()
    crewPhase.value = 'alert'
  }
  if (mode === 'manual' && crewPhase.value !== 'patrol') {
    crewPhase.value = 'returning'
    // 返回巡逻区的行走时长按距离计算,走完由 onCrewReturned 回到 patrol
  }
}

function selectRepelMode(mode) {
  if (executing.value || repelling.value) return
  selectedRepelMode.value = mode
}

const debugText = ref('')
// 仅用于开发期诊断贴图链路，可通过 ?debug=1 打开
const debugMode = typeof window !== 'undefined' && window.location.search.includes('debug=1')
if (debugMode) {
  setInterval(() => {
    if (handle && handle.debugTextureState) {
      try { debugText.value = JSON.stringify(handle.debugTextureState(), null, 1).slice(0, 900) } catch (e) { debugText.value = 'ERR ' + e.message }
    }
  }, 2000)
}

const autoRotate = ref(false)
function toggleRotate() {
  autoRotate.value = !autoRotate.value
  if (handle) handle.setAutoRotate(autoRotate.value)
}

/* ---------- 昼夜光照:默认跟随真实本地时间,滑杆手动演示 ---------- */
const daylightMode = ref('real')
const daylightHour = ref(12)
const realHour = ref(new Date().getHours() + new Date().getMinutes() / 60)
let daylightTimer = null
const daylightName = computed(() => {
  const h = daylightMode.value === 'manual' ? daylightHour.value : realHour.value
  const name = h < 5.4 ? '深夜' : h < 7.2 ? '黎明' : h < 11 ? '上午' : h < 14 ? '正午' : h < 17 ? '下午' : h < 19.2 ? '黄昏' : h < 20.5 ? '入夜' : '深夜'
  return `${name} · ${Math.floor(h)} 时`
})
function applyDaylight() {
  realHour.value = new Date().getHours() + new Date().getMinutes() / 60
  const h = daylightMode.value === 'manual' ? daylightHour.value : realHour.value
  if (handle && handle.setDaylight) handle.setDaylight(h)
}
function setDaylightMode(m) {
  daylightMode.value = m
  applyDaylight()
}
function onDaylightSlide(event) {
  daylightMode.value = 'manual'
  daylightHour.value = Number(event.target.value)
  applyDaylight()
}
watch(ready, r => {
  if (r) {
    applyDaylight()
    if (daylightTimer) clearInterval(daylightTimer)
    daylightTimer = setInterval(applyDaylight, 60000) // 实时模式每分钟跟随
  }
})
onBeforeUnmount(() => { if (daylightTimer) clearInterval(daylightTimer) })
</script>

<template>
  <div class="scene-root">
    <canvas ref="canvas" class="scene-canvas" />

    <!-- 加载遮罩：场景就绪即隐藏（登录表单在遮罩之上，未登录时也要露出来） -->
    <div class="hud-loading" :class="{ 'is-hidden': ready }">
      <div class="hud-loading__mark">青</div>
      <div class="hud-loading__text">{{ sceneError || (ready ? '等待登录' : '正在构建果园场景') }}</div>
      <div class="hud-loading__bar"><div class="hud-loading__fill" :style="{ width: loadProgress + '%' }" /></div>
    </div>

    <!-- 场景错误（WebGL 不可用等） -->
    <div v-if="sceneError && ready" class="login-mask">
      <div class="login-card">
        <div class="login-mark" style="background: var(--danger-fg)">!</div>
        <div class="login-title">无法加载 3D 场景</div>
        <div class="login-sub">{{ sceneError }}</div>
        <div class="login-hint">你可以尝试：更新浏览器、启用硬件加速、或换用 Chrome/Edge</div>
      </div>
    </div>

    <!-- 登录浮层 -->
    <div v-if="needLogin && ready && !sceneError" class="login-mask">
      <div class="login-card">
        <div class="login-mark">青</div>
        <div class="login-title">青禾 · 果园 3D 演示</div>
        <div class="login-sub">连接果园服务，查看低多边形场景与实时数据联动</div>

        <label class="login-label">服务地址</label>
        <input v-model="serverInput" class="login-input" placeholder="http://127.0.0.1:8008" />

        <label class="login-label">账号</label>
        <input v-model="username" class="login-input" placeholder="orchard" />

        <label class="login-label">密码</label>
        <input
          v-model="password"
          type="password"
          class="login-input"
          placeholder="启动终端显示的密码"
          @keyup.enter="doLogin"
        />

        <div v-if="loginError" class="login-error">{{ loginError }}</div>

        <button class="login-btn" :disabled="loggingIn || !password" @click="doLogin">
          {{ loggingIn ? '正在连接…' : '进入 3D 果园' }}
        </button>

        <div class="login-hint">账号由本地服务创建，与手机端一致</div>
      </div>
    </div>

    <!-- 顶部 HUD -->
    <div class="hud-top">
      <div class="hud-brand">
        <div class="hud-brand__row">
          <span class="hud-brand__name">青禾示范果园</span>
          <span class="hud-brand__tag">3D</span>
        </div>
      <span class="hud-brand__site">东区 · 01 号监控点 · 果园数字沙盘</span>
      </div>
      <div class="hud-badges">
        <span :class="badgeClass"><i class="hud-badge__dot" />{{ monitorLabel }}</span>
        <span class="hud-badge" :class="{ 'is-warn': !state.connected }">
          <i class="hud-badge__dot" />{{ state.connected ? '实时连接' : '连接中断' }}
        </span>
      </div>
    </div>

    <!-- 左侧：远程驱离控制与果农协作 -->
    <aside class="hud-panel hud-panel--control" :class="{ 'is-collapsed': controlCollapsed }">
      <div class="hud-panel__head">
        <div><strong>远程驱离控制</strong><span>{{ crewPhaseLabel }}</span></div>
        <button class="hud-panel__toggle" :aria-expanded="!controlCollapsed" @click="togglePanel('control')">{{ controlCollapsed ? '展开' : '收起' }}</button>
      </div>

      <template v-if="!controlCollapsed">
        <div class="hud-card hud-control-card">
          <div class="hud-card__title">响应方式</div>
          <div class="response-switch">
            <button :class="{ 'is-active': responseMode === 'manual' }" :disabled="executing || repelling" @click="setResponseMode('manual')">手动控制</button>
            <button :class="{ 'is-active': responseMode === 'auto' }" :disabled="executing || repelling" @click="setResponseMode('auto')">自动响应</button>
          </div>
          <p class="response-help">{{ responseMode === 'auto' ? '发现鸟类后果农沿道路出动；到达设备旁才启动驱离。' : '手动模式下果农在三个区块日常巡逻，由你选择设备直接驱离。' }}</p>
          <div v-if="responseMode === 'manual'" class="repel-modes">
            <button :class="{ 'is-selected': selectedRepelMode === 'acoustic' }" :disabled="executing || repelling" @click="selectRepelMode('acoustic')">声波</button>
            <button :class="{ 'is-selected': selectedRepelMode === 'infrared' }" :disabled="executing || repelling" @click="selectRepelMode('infrared')">红外</button>
            <button :class="{ 'is-selected': selectedRepelMode === 'both' }" :disabled="executing || repelling" @click="selectRepelMode('both')">双模</button>
          </div>
          <button class="hud-action hud-action--repel hud-control-submit" :class="{ 'is-done': repelDone, 'is-executing': executing }" :disabled="responseMode === 'auto' || !birdCount || executing || repelling || offline || !state.token" @click="repel(effectiveRepelMode, false)">
            {{ repelDone ? '指令完成 · 待复核' : responseMode === 'auto' ? crewPhase === 'patrol' ? '自动响应已就绪' : crewPhase === 'working' ? '果农正在前往设备…' : crewPhase === 'positioned' ? '果农已到位 · 正在启动' : crewPhase === 'actuating' ? '设备驱离执行中…' : '等待自动流程' : repelling ? '正在下发…' : executing ? '驱离执行中…' : birdCount ? `模拟驱离 · ${birdCount} 只示意鸟` : '等待检测到鸟类' }}
          </button>
          <div class="control-footnote">{{ responseMode === 'auto' ? '设备抵达判定已开启 · 模拟执行器' : '手动触发不派出果农 · 模拟执行器' }}</div>
        </div>

        <div class="hud-card crew-card">
          <div class="crew-card__head">
            <div>
              <div class="hud-card__title">果农响应流程</div>
              <span class="crew-card__phase">{{ crewPhaseLabel }}</span>
            </div>
            <button class="crew-card__toggle" @click="crewExpanded = !crewExpanded">{{ crewExpanded ? '收起' : '展开' }}</button>
          </div>
          <div v-if="crewExpanded" class="crew-steps">
            <template v-for="(task, index) in crewTasks" :key="task.key">
              <div class="crew-step" :class="{ 'is-active': index === crewStepIndex, 'is-done': index < crewStepIndex, 'is-muted': !task.enabled }">
                <span class="crew-step__dot">{{ index < crewStepIndex ? '✓' : '0' + (index + 1) }}</span>
                <span class="crew-step__name">{{ task.title }}</span>
              </div>
              <i v-if="index < crewTasks.length - 1" class="crew-step__line" :class="{ 'is-done': index < crewStepIndex }" />
            </template>
          </div>
          <div v-if="crewExpanded" class="crew-step__status-line">
            <span>{{ crewPhaseLabel }}</span>
            <span class="crew-step__detail">{{ crewTasks[Math.max(0, Math.min(crewStepIndex, 2))]?.detail || '三名果农分区巡逻中' }}</span>
          </div>
        </div>

        <div class="hud-card daylight-card">
          <div class="crew-card__head">
            <div><div class="hud-card__title">场景设置</div><span class="crew-card__phase">{{ daylightName }}</span></div>
            <button class="crew-card__toggle" :aria-expanded="daylightExpanded" @click="daylightExpanded = !daylightExpanded">{{ daylightExpanded ? '收起' : '展开' }}</button>
          </div>
          <template v-if="daylightExpanded">
          <div class="daylight-switch">
            <button :class="{ 'is-active': daylightMode === 'real' }" @click="setDaylightMode('real')">实时</button>
            <button :class="{ 'is-active': daylightMode === 'manual' }" @click="setDaylightMode('manual')">手动</button>
          </div>
          <input class="daylight-slider" aria-label="场景光照时间" type="range" min="0" max="24" step="0.25"
            :value="daylightMode === 'manual' ? daylightHour : realHour"
            :disabled="daylightMode === 'real'" @input="onDaylightSlide" />
          <div class="daylight-scale"><span>0</span><span>6</span><span>12</span><span>18</span><span>24</span></div>
          <div class="daylight-readout mono">{{ daylightName }}</div>
          <div class="daylight-hint">拖动滑杆预览晨昏与夜间光照</div>
          </template>
        </div>

      </template>
    </aside>

    <!-- 右侧：果园概览、检测记录与设备遥测 -->
    <aside class="hud-panel hud-panel--info" :class="{ 'is-collapsed': infoCollapsed }">
      <div class="hud-panel__head">
        <div><strong>果园运行数据</strong><span>检测与模拟设备状态</span></div>
        <button class="hud-panel__toggle" :aria-expanded="!infoCollapsed" @click="togglePanel('info')">{{ infoCollapsed ? '展开' : '收起' }}</button>
      </div>
      <template v-if="!infoCollapsed">
        <div class="hud-card">
          <div class="hud-card__title">果园概览</div>
          <div class="hud-stats">
            <div class="hud-stat"><span class="hud-stat__num is-warn">{{ state.counts.pending }}</span><span class="hud-stat__label">待处理告警</span></div>
            <div class="hud-stat"><span class="hud-stat__num">{{ state.counts.total }}</span><span class="hud-stat__label">检测事件</span></div>
            <div class="hud-stat"><span class="hud-stat__num">{{ state.counts.completed }}</span><span class="hud-stat__label">模拟执行</span></div>
          </div>
        </div>

        <div class="hud-card">
          <div class="hud-card__title">最近检测 · 位置示意</div>
          <p class="detection-count">最新帧检出 {{ detectedCount }} 只 · 场景示意 {{ birdCount }} 只</p>
          <template v-if="recentAlarms.length">
            <div v-for="a in recentAlarms" :key="a.id" class="hud-detect">
              <i class="hud-detect__dot" :class="{ 'is-alarm': a.status === 'new' }" />
              <div class="hud-detect__body"><span class="hud-detect__name">{{ a.species }} · {{ a.count }} 只</span><span class="hud-detect__meta">{{ timeText(a.at) }} · {{ (a.confidence * 100).toFixed(0) }}%</span></div>
              <button v-if="hasBbox(a)" class="hud-detect__locate" :class="{ 'is-on': focusTarget === a.id }" @click="focusAlarm(a)">{{ focusTarget === a.id ? '返回' : '查看' }}</button>
            </div>
          </template>
          <div v-else class="hud-empty">开始检测后，这里显示最新识别结果</div>
          <figure v-if="focusedAlarm" class="capture-detail">
            <img v-if="focusedCapture && !captureFailed" :src="focusedCapture" :alt="focusedAlarm.species + '检测抓拍'" @error="captureFailed = true" />
            <p v-else class="hud-empty">{{ captureFailed ? '抓拍暂时无法加载' : '暂无抓拍照片' }}</p>
            <figcaption>{{ focusedAlarm.species }} · 历史抓拍，场景位置仅供示意</figcaption>
          </figure>
        </div>

        <div class="hud-card">
          <div class="hud-card__title">模拟设备</div>
          <div class="hud-device"><div class="hud-device__icon">◉</div><div class="hud-device__body"><span class="hud-device__name">声学驱鸟器 01</span><span class="hud-device__desc">{{ acousticDesc }}</span></div><span class="hud-pill" :class="{ 'is-off': offline }"><i class="hud-pill__dot" />{{ offline ? '离线' : '在线' }}</span></div>
          <div class="hud-device" style="margin-top: 8px;"><div class="hud-device__icon" style="color: #ef6472;">◎</div><div class="hud-device__body"><span class="hud-device__name">红外驱鸟器 02</span><span class="hud-device__desc">{{ irDesc }}</span></div><span class="hud-pill" :class="{ 'is-off': offline }"><i class="hud-pill__dot" />{{ offline ? '离线' : '在线' }}</span></div>
        </div>
      </template>
    </aside>

    <!-- 底部图例与操作 -->
    <div class="hud-bottom">
      <div class="hud-legend">
        <span class="hud-legend__item">
          <i class="hud-legend__swatch" style="background: #d3e856" />检测框
        </span>
        <span class="hud-legend__item">
          <i class="hud-legend__swatch" style="background: #e0a03a" />告警标记
        </span>
        <span class="hud-legend__item">
          <i class="hud-legend__swatch" style="background: #7b9b63" />果树
        </span>
        <span class="hud-legend__item">
          <i class="hud-legend__swatch" style="background: #8d9491" />监测设备
        </span>
        <span class="hud-legend__item">
          <i class="hud-legend__swatch" style="background: #f04438" />红外光束
        </span>
      </div>
      <div style="display: flex; align-items: center; gap: 12px; pointer-events: auto">
        <div v-if="repelMsg" class="repel-msg" :class="{ 'is-warn': repelFail }">{{ repelMsg }}</div>
        <button class="hud-action" @click="toggleRotate">{{ autoRotate ? '停止环绕' : '自动环绕' }}</button>
        <button class="hud-action" @click="resetView">重置视角</button>
      </div>
    </div>

    <div class="hud-note-abs">空间位置与鸟群动画为示意 · 驱离效果以监控复核为准</div>
    <div v-if="debugText" style="position:absolute;left:8px;top:70px;font:11px monospace;color:#d3e856;background:rgba(0,0,0,.7);padding:6px;border-radius:4px;max-width:520px;white-space:pre-wrap;z-index:60">{{ debugText }}</div>
  </div>
</template>

<style scoped>
.scene-root {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

/* ---------- 登录浮层 ---------- */
.login-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(16, 22, 14, 0.72);
  backdrop-filter: blur(6px);
  z-index: 45;
}

.login-card {
  width: 340px;
  padding: 28px 24px 24px;
  border-radius: var(--radius-2xl);
  background: var(--surface-raised);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.login-mark {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--brand-700);
  color: #f5f7ec;
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 10px;
  box-shadow: 0 6px 18px rgba(52, 80, 47, 0.35);
}

.login-title {
  font-family: var(--font-serif);
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--ink-900);
  text-align: center;
}

.login-sub {
  font-size: var(--text-xs);
  color: var(--ink-400);
  text-align: center;
  margin-bottom: 12px;
  line-height: 1.6;
}

.login-label {
  font-size: var(--text-xs);
  color: var(--ink-500);
  font-weight: 500;
  margin-top: 8px;
}

.login-input {
  height: 42px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--line-strong);
  background: var(--surface-card);
  font-family: var(--font-sans);
  font-size: var(--text-md);
  color: var(--ink-900);
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.login-input:focus {
  border-color: var(--brand-700);
  box-shadow: 0 0 0 3px rgba(52, 80, 47, 0.13);
}

.login-error {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: var(--danger-bg);
  border: 1px solid rgba(156, 85, 70, 0.24);
  color: var(--danger-fg);
  font-size: var(--text-xs);
}

.login-btn {
  margin-top: 16px;
  height: 46px;
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--brand-700);
  color: #f5f7ec;
  font-family: var(--font-sans);
  font-size: var(--text-lg);
  font-weight: 500;
  letter-spacing: 2px;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(41, 61, 33, 0.25);
  transition: background 0.15s ease, transform 0.15s ease;
}
.login-btn:active:not(:disabled) {
  background: var(--brand-800);
  transform: scale(0.985);
}
.login-btn:disabled {
  background: #d9dcc9;
  color: #98a08b;
  box-shadow: none;
  cursor: not-allowed;
}

.login-hint {
  margin-top: 12px;
  font-size: var(--text-2xs);
  color: var(--ink-300);
  text-align: center;
}

/* ---------- 底部操作按钮 ---------- */
.hud-action {
  pointer-events: auto;
  padding: 7px 14px;
  border-radius: var(--radius-pill);
  border: 1px solid rgba(52, 80, 47, 0.16);
  background: rgba(255, 255, 255, 0.94);
  color: var(--brand-800);
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  font-weight: 500;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition: background 0.15s ease, transform 0.15s ease;
}
.hud-action:hover {
  background: var(--brand-100);
  transform: translateY(-1px);
}

/* 声波驱离按钮：告警橙，突出主操作 */
.hud-action--repel {
  background: linear-gradient(115deg, #24b69b, #237e85);
  border-color: rgba(113, 239, 207, .72);
  color: #f4fffb;
  font-weight: 600;
  box-shadow: 0 4px 16px rgba(18, 184, 151, .24), inset 0 1px rgba(255,255,255,.22);
}
.hud-action--repel:hover:not(:disabled) {
  background: linear-gradient(115deg, #32c9aa, #27959a);
  color: #fff;
  box-shadow: 0 5px 20px rgba(18, 205, 170, .34), inset 0 1px rgba(255,255,255,.25);
}
.hud-action--repel:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.hud-action--repel.is-executing { animation: qhBlink 1.4s steps(2) infinite; }
.hud-action--repel.is-done {
  background: linear-gradient(115deg, #2f9e6e, #1f7d5c);
  border-color: rgba(89, 225, 182, .72);
  box-shadow: 0 4px 16px rgba(47, 178, 126, .3), inset 0 1px rgba(255,255,255,.22);
}

.hud-panel {
  width: 270px;
  top: 78px;
  right: 24px;
  max-height: calc(100vh - 148px);
  overflow-y: auto;
  padding: 2px;
  scrollbar-width: thin;
  scrollbar-color: #6e9d8e transparent;
}
.hud-panel--control { left: 24px; right: auto; }
.hud-panel--info { width: 248px; left: auto; right: 24px; }
.hud-panel.is-collapsed { width: auto; max-height: none; overflow: visible; }
.hud-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(97, 208, 184, 0.24);
  border-radius: var(--radius-xl);
  background: linear-gradient(135deg, rgba(9, 27, 31, 0.94), rgba(15, 47, 47, 0.9));
  box-shadow: 0 12px 30px rgba(3, 18, 21, 0.3), inset 0 1px rgba(158, 243, 219, 0.09);
  backdrop-filter: blur(16px);
  margin-bottom: var(--space-3);
}
.hud-panel__head > div { display: flex; flex-direction: column; gap: 3px; }
.hud-panel__head strong { color: #effcf7; font-size: var(--text-sm); letter-spacing: .3px; }
.hud-panel__head span { color: #83cbb7; font: 9px var(--font-num); letter-spacing: .55px; }
.hud-panel__toggle, .crew-card__toggle {
  border: 0;
  padding: 5px 8px;
  border-radius: var(--radius-sm);
  color: #a5f3dd;
  background: rgba(62, 172, 149, .16);
  border: 1px solid rgba(95, 218, 190, .18);
  font: inherit;
  font-size: var(--text-2xs);
  cursor: pointer;
}
.hud-panel .hud-card {
  color: #e5f3ee;
  border-color: rgba(102, 191, 172, .2);
  background:
    linear-gradient(135deg, rgba(10, 28, 32, .78), rgba(13, 40, 41, .72)),
    repeating-linear-gradient(0deg, transparent 0 23px, rgba(95, 218, 190, .025) 24px);
  box-shadow: 0 12px 28px rgba(4, 18, 22, .28), inset 0 1px rgba(193, 255, 235, .055);
  backdrop-filter: blur(16px);
}
.hud-panel .hud-card__title { color: #80cdb9; letter-spacing: .6px; }
.hud-panel .hud-stat__num { color: #edf9f3; text-shadow: 0 0 14px rgba(99, 235, 199, .16); }
.hud-panel .hud-stat__num.is-warn { color: #ffc66e; }
.hud-panel .hud-stat__label, .hud-panel .hud-detect__meta { color: #8eaaa4; }
.hud-panel .hud-detect__name, .hud-panel .hud-device__name, .hud-panel .crew-task__body strong { color: #e9f6f0; }
.hud-panel .hud-device__desc, .hud-panel .hud-empty, .hud-panel .crew-task__body span { color: #8eaaa4; }
.hud-panel .hud-device__icon { background: rgba(73, 163, 145, .14); color: #78ddc2; }
.hud-panel .hud-pill { color: #8ce7c1; background: rgba(36, 102, 75, .22); border-color: rgba(91, 207, 154, .22); }
.hud-panel .hud-pill__dot { background: #70e3ae; box-shadow: 0 0 8px rgba(112, 227, 174, .75); }
.hud-panel .hud-pill.is-off { color: #ffc07d; background: rgba(143, 83, 43, .22); border-color: rgba(246, 164, 91, .3); }
.hud-panel .hud-pill.is-off .hud-pill__dot { background: #ffad67; }
.hud-control-card, .crew-card { padding: 14px; }
.response-switch, .repel-modes { display: grid; gap: 6px; }
.response-switch { grid-template-columns: 1fr 1fr; }
.repel-modes { grid-template-columns: repeat(3, 1fr); margin: 10px 0; }
.response-switch button, .repel-modes button {
  min-height: 36px;
  border: 1px solid rgba(126, 188, 176, .22);
  border-radius: var(--radius-sm);
  color: #b6cec7;
  background: rgba(4, 18, 23, .55);
  font: inherit;
  font-size: var(--text-xs);
  cursor: pointer;
  transition: background .15s ease, border-color .15s ease, color .15s ease;
}
.response-switch button.is-active, .repel-modes button.is-selected {
  color: #edfff8;
  background: linear-gradient(135deg, rgba(30, 161, 137, .8), rgba(34, 111, 112, .78));
  border-color: rgba(105, 238, 206, .6);
  font-weight: 600;
  box-shadow: 0 0 16px rgba(50, 216, 177, .16), inset 0 1px rgba(255,255,255,.16);
}
.response-switch button:disabled, .repel-modes button:disabled { opacity: .55; cursor: not-allowed; }
.response-help { margin: 8px 0 0; color: #a4c1b8; font-size: var(--text-2xs); line-height: 1.6; }
.hud-control-submit { width: 100%; justify-content: center; margin-top: 2px; }
.control-footnote { margin-top: 8px; color: #779991; font-size: var(--text-2xs); text-align: center; }
.crew-card__head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.crew-card__head .hud-card__title { margin: 0 0 3px; }
.crew-card__phase { color: #70dfc0; font-size: var(--text-2xs); }
.crew-task-list { display: flex; flex-direction: column; gap: 2px; }
.crew-task { display: flex; align-items: center; gap: 9px; padding: 8px 0; border-top: 1px solid rgba(99,185,166,.16); }
.crew-task__index { width: 25px; height: 25px; border: 1px solid rgba(97,221,192,.23); border-radius: 50%; display: grid; place-items: center; flex: 0 0 auto; background: rgba(43,156,134,.16); color: #8be8cc; font: 600 10px var(--font-num); box-shadow: inset 0 0 12px rgba(62,202,170,.08); }
.crew-task__body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.crew-task__body strong { color: var(--ink-800); font-size: var(--text-xs); font-weight: 600; }
.crew-task__body span { color: var(--ink-400); font-size: 10px; }
.crew-task__body small { color: #74d9ba; font-size: 10px; }
.crew-task.is-muted .crew-task__body small { color: var(--ink-300); }
.crew-task__status { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 auto; background: rgba(133,164,157,.42); }
.crew-task__status.is-active { background: #ff5e69; box-shadow: 0 0 0 4px rgba(255,84,99,.15), 0 0 12px rgba(255,84,99,.72); }
.crew-task__status.is-done { background: #59e1b6; box-shadow: 0 0 0 4px rgba(89,225,182,.13), 0 0 10px rgba(89,225,182,.56); }
.crew-collapsed-note { padding-top: 8px; border-top: 1px solid rgba(99,185,166,.16); color: #a4c1b8; font-size: var(--text-xs); }

/* 果农流程横向步骤条 */
.crew-steps { display: flex; align-items: flex-start; gap: 4px; padding: 4px 0 2px; }
.crew-step { display: flex; flex-direction: column; align-items: center; gap: 4px; flex: 1; min-width: 0; }
.crew-step__dot { width: 24px; height: 24px; border-radius: 50%; border: 1px solid rgba(97,221,192,.35); display: grid; place-items: center; font: 600 10px var(--font-num); color: #8be8cc; background: rgba(43,156,134,.14); }
.crew-step.is-active .crew-step__dot { border-color: #ff5e69; color: #fff; background: rgba(255,84,99,.28); box-shadow: 0 0 10px rgba(255,84,99,.5); }
.crew-step.is-done .crew-step__dot { background: #59e1b6; color: #0e2a20; border-color: #59e1b6; }
.crew-step.is-muted { opacity: .45; }
.crew-step__name { font-size: 9.5px; color: var(--ink-400); text-align: center; line-height: 1.3; }
.crew-step.is-active .crew-step__name { color: #e5f3ee; font-weight: 600; }
.crew-step.is-done .crew-step__name { color: #74d9ba; }
.crew-step__line { flex: 1; height: 1px; background: rgba(97,221,192,.3); margin-top: 12px; }
.crew-step__line.is-done { background: #59e1b6; }
.crew-step__status-line { padding: 6px 8px; border-radius: var(--radius-md); background: rgba(43,156,134,.12); display: flex; flex-direction: column; gap: 2px; }
.crew-step__status-line span:first-child { color: #74d9ba; font-size: 10px; font-weight: 600; }
.crew-step__detail { color: var(--ink-400); font-size: 10px; }

/* 最近检测定位按钮 */
.hud-detect__locate { flex: 0 0 auto; border: 1px solid rgba(97,221,192,.35); background: rgba(43,156,134,.12); color: #8be8cc; font-size: 11px; font-weight: 600; min-height: 36px; padding: 6px 8px; cursor: pointer; }
.hud-detect__locate.is-on { background: rgba(89,225,182,.22); color: #b8f5dd; border-color: #59e1b6; }

/* 驱离操作反馈 */
.repel-msg {
  padding: 6px 12px;
  border-radius: var(--radius-pill);
  background: var(--success-bg);
  border: 1px solid var(--success-fg);
  color: var(--success-fg);
  font-size: var(--text-xs);
  font-weight: 500;
  white-space: nowrap;
  box-shadow: var(--shadow-sm);
}

/* 未驱走：告警橙提示 */
.repel-msg.is-warn {
  background: var(--warn-bg);
  border-color: var(--warn-line);
  color: var(--warn-fg);
}

.hud-note-abs {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  bottom: 78px;
  font-size: var(--text-2xs);
  color: var(--ink-700);
  letter-spacing: 0.2px;
  padding: 6px 11px;
  border-radius: var(--radius-pill);
  background: rgba(251, 250, 243, 0.88);
  box-shadow: var(--shadow-sm);
  pointer-events: none;
  z-index: 10;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .hud-panel { display: flex; width: min(300px, calc(100vw - 18px)); max-height: calc(100vh - 126px); }
  .hud-panel--control { left: 9px; right: auto; top: 68px; }
  .hud-panel--info { left: auto; right: 9px; top: 68px; }
  .hud-panel:not(.is-collapsed) { top: 126px; left: 9px; right: 9px; width: auto; max-height: calc(100dvh - 210px); }
  .hud-panel.is-collapsed .hud-panel__head span { display: none; }
  .hud-panel__head { padding: 8px; gap: 6px; }
  .hud-panel__head strong { font-size: 12px; }
  .hud-panel button { min-height: 40px; }
  .hud-bottom { padding: 10px; }
  .hud-legend { display: none; }
  .repel-msg { position: fixed; bottom: 64px; left: 10px; right: 10px; white-space: normal; }
  .hud-panel.is-collapsed { width: auto; }
  .hud-note-abs { display: none; }
  .login-card { width: 92vw; }
}

/* ---- 光照演示卡 ---- */
.daylight-card .daylight-switch { display: flex; gap: 6px; margin-bottom: 8px; }
.daylight-card .daylight-switch button { flex: 1; border: 1px solid rgba(212, 232, 86, .35); background: transparent; color: inherit; padding: 5px 0; font-size: 12px; cursor: pointer; opacity: .65; }
.daylight-card .daylight-switch button.is-active { opacity: 1; background: rgba(212, 232, 86, .14); border-color: #d3e856; }
.daylight-card .daylight-slider { width: 100%; accent-color: #d3e856; }
.daylight-card .daylight-slider:disabled { opacity: .35; }
.daylight-card .daylight-scale { display: flex; justify-content: space-between; font-size: 10px; opacity: .5; }
.daylight-card .daylight-readout { margin-top: 6px; font-size: 13px; font-weight: 700; letter-spacing: 1px; }
.daylight-card .daylight-hint { margin-top: 4px; font-size: 11px; opacity: .55; line-height: 1.5; }
button:focus-visible, input:focus-visible { outline: 2px solid #d3e856; outline-offset: 3px; }
.hud-panel .hud-card { background: rgba(15, 36, 33, .91); box-shadow: 0 8px 24px rgba(4, 18, 22, .18); }
.hud-panel .hud-stat__label, .hud-panel .hud-detect__meta, .hud-panel .hud-device__desc, .control-footnote { color: #b9d0c8; }
.crew-card__head { margin-bottom: 0; }
.crew-step__name, .crew-step__detail { color: #b9d0c8; }
.daylight-card .daylight-switch { margin-top: 12px; }
.detection-count { font-size: 11px; line-height: 1.5; color: #b9d0c8; margin: 0 0 8px; }
.capture-detail { margin: 12px 0 0; }
.capture-detail img { width: 100%; display: block; border-radius: 6px; }
.capture-detail figcaption { margin-top: 6px; font-size: 11px; line-height: 1.5; color: #b9d0c8; }

/* ---- 声波音效开关 ---- */
.sound-row { display: flex; align-items: center; gap: 8px; margin-top: 9px; }
.sound-toggle { display: flex; align-items: center; gap: 6px; border: 1px solid rgba(97,221,192,.35); background: rgba(43,156,134,.1); color: #8be8cc; font-size: 11px; font-weight: 600; padding: 5px 10px; cursor: pointer; border-radius: var(--radius-sm); }
.sound-toggle.is-on { background: rgba(89,225,182,.2); border-color: #59e1b6; color: #b8f5dd; }
.sound-toggle__dot { width: 7px; height: 7px; border-radius: 50%; background: rgba(133,164,157,.5); }
.sound-toggle.is-on .sound-toggle__dot { background: #59e1b6; box-shadow: 0 0 8px rgba(89,225,182,.6); }
.sound-hint { font-size: 10px; opacity: .55; }
</style>
