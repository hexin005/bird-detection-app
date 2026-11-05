/**
 * 与后端 /api/ws 通信的数据层
 * ---------------------------------------------------------------------------
 * 复用 H5 端 store.ts 的协议：
 *   1. POST /api/login 拿 token
 *   2. WebSocket 连接后先发 { token } 完成鉴权
 *   3. 后端每 0.6 秒推送一次完整快照
 */
import { reactive } from 'vue'

export const state = reactive({
  connected: false,
  connecting: false,
  error: '',
  token: '',
  server: '',
  /** 后端快照原始数据 */
  snapshot: null,
  /** monitor.status: idle | starting | running | stopping | stopped | ended | interrupted | error */
  monitorStatus: 'idle',
  monitorMessage: '',
  /** 当前帧检测结果 */
  detections: [],
  /** 告警列表 */
  alarms: [],
  /** 指令列表 */
  commands: [],
  /** 计数 */
  counts: { total: 0, pending: 0, completed: 0 },
  /** 设备场景：normal | offline | timeout */
  scenario: 'normal',
  /** 当前活动指令 */
  activeCommand: null,
  /** 媒体票据 */
  mediaTicket: '',
})

let socket = null
let reconnectTimer = null
let reconnectDelay = 2000
let manualClose = false

function normalizeUrl(url) {
  return url.replace(/\/$/, '')
}

/** 默认服务地址：同源（由 FastAPI 提供页面时）或开发时的 localhost:8008 */
export function defaultServer() {
  if (typeof window === 'undefined') return 'http://127.0.0.1:8008'
  const { protocol, hostname, port } = window.location
  // 开发服务器 5180：走 vite 代理，直接用同源
  if (port === '5180') return ''
  return `${protocol}//${hostname}${port ? ':' + port : ''}`
}

function syncFromSnapshot(data) {
  if (!data) return
  state.snapshot = data
  const monitor = data.monitor || {}
  state.monitorStatus = monitor.status || 'idle'
  state.monitorMessage = monitor.message || ''
  state.detections = (monitor.frame && Array.isArray(monitor.frame.detections)) ? monitor.frame.detections : []
  state.alarms = Array.isArray(data.alarms) ? data.alarms : []
  state.commands = Array.isArray(data.commands) ? data.commands : []
  state.counts = data.counts || { total: 0, pending: 0, completed: 0 }
  state.scenario = (data.settings && data.settings.scenario) || 'normal'
  state.mediaTicket = data.media_ticket || ''
  state.activeCommand = state.commands.find((c) => c.status === 'pending' || c.status === 'running') || null
}

/** 登录并建立 WebSocket */
export async function connect(username, password) {
  const server = normalizeUrl(state.server || defaultServer())
  state.server = server
  state.error = ''
  state.connecting = true
  manualClose = true
  closeSocket()
  manualClose = false

  try {
    const res = await fetch(`${server}/api/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      throw new Error(detail.detail || '账号或密码错误')
    }
    const data = await res.json()
    state.token = data.token
    state.connecting = false
    openSocket()
    // 立即拉一次快照，避免等 WebSocket 首帧
    const initial = await fetch(`${server}/api/state`, {
      headers: { Authorization: 'Bearer ' + state.token },
    })
    if (initial.ok) syncFromSnapshot(await initial.json())
    return true
  } catch (err) {
    state.connecting = false
    state.error = err.message || '连接失败'
    return false
  }
}

function openSocket() {
  const server = state.server || defaultServer()
  const wsBase = server
    ? server.replace(/^http/, 'ws')
    : (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host
  const url = `${wsBase}/api/ws`

  try {
    socket = new WebSocket(url)
  } catch (err) {
    state.error = 'WebSocket 创建失败'
    scheduleReconnect()
    return
  }

  socket.onopen = () => {
    state.connected = true
    state.error = ''
    reconnectDelay = 2000
    socket.send(JSON.stringify({ token: state.token }))
  }

  socket.onmessage = (event) => {
    try {
      syncFromSnapshot(JSON.parse(event.data))
    } catch {
      /* 忽略不完整消息 */
    }
  }

  socket.onclose = () => {
    state.connected = false
    if (!manualClose) scheduleReconnect()
  }

  socket.onerror = () => {
    state.connected = false
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    if (state.token && !manualClose) openSocket()
    reconnectDelay = Math.min(reconnectDelay * 1.5, 15000)
  }, reconnectDelay)
}

function closeSocket() {
  if (socket) {
    try { socket.close() } catch { /* ignore */ }
    socket = null
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  state.connected = false
}

export function disconnect() {
  manualClose = true
  closeSocket()
  state.token = ''
  state.snapshot = null
}
