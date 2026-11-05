<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { createOrchardScene } from './lib/renderer.js'
import { state, connect, disconnect, defaultServer } from './lib/data.js'

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

const timeText = (at) => {
  if (!at) return ''
  const d = new Date(at * 1000)
  return d.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' })
}

/* ---------- 把业务状态喂给 3D ---------- */
function pushStateToScene() {
  if (!handle) return
  handle.setState({
    running: state.monitorStatus === 'running' || state.monitorStatus === 'starting',
    detections: state.detections,
    alarms: state.alarms.filter((a) => a.status === 'new'),
    executing: executing.value,
    offline: offline.value,
  })
}

watch(
  () => [
    state.monitorStatus,
    state.detections.length,
    state.alarms.length,
    state.activeCommand && state.activeCommand.id,
    state.scenario,
  ],
  pushStateToScene,
  { deep: false },
)

/* ---------- 生命周期 ---------- */
onMounted(() => {
  loadProgress.value = 30
  handle = createOrchardScene(canvas.value, {
    onReady: () => {
      loadProgress.value = 100
      ready.value = true
    },
  })

  serverInput.value = defaultServer() || window.location.origin
  // 若已有 token（同源共享 localStorage）直接连
  const savedToken = localStorage.getItem('bird-scene-token')
  const savedServer = localStorage.getItem('bird-scene-server')
  if (savedToken && savedServer) {
    state.token = savedToken
    state.server = savedServer
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
  if (handle) handle.dispose()
  disconnect()
})

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
  if (handle) handle.resetView()
}

const autoRotate = ref(true)
function toggleRotate() {
  autoRotate.value = !autoRotate.value
  if (handle) handle.setAutoRotate(autoRotate.value)
}
</script>

<template>
  <div class="scene-root">
    <canvas ref="canvas" class="scene-canvas" />

    <!-- 加载遮罩 -->
    <div class="hud-loading" :class="{ 'is-hidden': ready && !needLogin }">
      <div class="hud-loading__mark">青</div>
      <div class="hud-loading__text">{{ ready ? '等待登录' : '正在构建果园场景' }}</div>
      <div class="hud-loading__bar"><div class="hud-loading__fill" :style="{ width: loadProgress + '%' }" /></div>
    </div>

    <!-- 登录浮层 -->
    <div v-if="needLogin && ready" class="login-mask">
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
        <span class="hud-brand__site">东区 · 01 号监控点 · 低多边形演示场景</span>
      </div>
      <div class="hud-badges">
        <span :class="badgeClass"><i class="hud-badge__dot" />{{ monitorLabel }}</span>
        <span class="hud-badge" :class="{ 'is-warn': !state.connected }">
          <i class="hud-badge__dot" />{{ state.connected ? '实时连接' : '连接中断' }}
        </span>
      </div>
    </div>

    <!-- 右侧面板 -->
    <aside class="hud-panel">
      <div class="hud-card">
        <div class="hud-card__title">果园概览</div>
        <div class="hud-stats">
          <div class="hud-stat">
            <span class="hud-stat__num is-warn">{{ state.counts.pending }}</span>
            <span class="hud-stat__label">待处理告警</span>
          </div>
          <div class="hud-stat">
            <span class="hud-stat__num">{{ state.counts.total }}</span>
            <span class="hud-stat__label">检测事件</span>
          </div>
          <div class="hud-stat">
            <span class="hud-stat__num">{{ state.counts.completed }}</span>
            <span class="hud-stat__label">模拟执行</span>
          </div>
        </div>
      </div>

      <div class="hud-card">
        <div class="hud-card__title">最近检测</div>
        <template v-if="recentAlarms.length">
          <div v-for="a in recentAlarms" :key="a.id" class="hud-detect">
            <i class="hud-detect__dot" :class="{ 'is-alarm': a.status === 'new' }" />
            <div class="hud-detect__body">
              <span class="hud-detect__name">{{ a.species }} · {{ a.count }} 只</span>
              <span class="hud-detect__meta">{{ timeText(a.at) }} · {{ (a.confidence * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </template>
        <div v-else class="hud-empty">开始检测后，这里显示最新识别结果</div>
      </div>

      <div class="hud-card">
        <div class="hud-card__title">设备状态</div>
        <div class="hud-device">
          <div class="hud-device__icon">◉</div>
          <div class="hud-device__body">
            <span class="hud-device__name">声学驱鸟器 01</span>
            <span class="hud-device__desc">{{ executing ? '正在执行声波驱离' : '模拟设备 · 待命' }}</span>
          </div>
          <span class="hud-pill" :class="{ 'is-off': offline }">
            <i class="hud-pill__dot" />{{ offline ? '离线' : '在线' }}
          </span>
        </div>
      </div>
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
      </div>
      <div style="display: flex; align-items: center; gap: 12px; pointer-events: auto">
        <button class="hud-action" @click="toggleRotate">{{ autoRotate ? '停止环绕' : '自动环绕' }}</button>
        <button class="hud-action" @click="resetView">重置视角</button>
      </div>
    </div>

    <div class="hud-note-abs">低多边形可视化 · 数据来自果园服务 · 驱鸟设备为模拟执行器</div>
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
  z-index: 30;
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
  border: 1px solid rgba(242, 244, 232, 0.22);
  background: rgba(35, 43, 29, 0.6);
  color: #dfe4d3;
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  font-weight: 500;
  cursor: pointer;
  backdrop-filter: blur(8px);
  transition: background 0.15s ease;
}
.hud-action:hover {
  background: rgba(52, 80, 47, 0.85);
  color: #f2f4e8;
}

.hud-note-abs {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  bottom: 78px;
  font-size: var(--text-2xs);
  color: rgba(242, 244, 232, 0.42);
  letter-spacing: 1px;
  pointer-events: none;
  z-index: 10;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .hud-note-abs { display: none; }
  .login-card { width: 92vw; }
}
</style>
