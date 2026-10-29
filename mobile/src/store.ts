import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { State, Command } from './types'

function defaultServer() {
  let url = ''
  // #ifdef H5
  url = window.location.origin
  // #endif
  return url
}

export class ApiError extends Error { constructor(message: string, public status: number) { super(message) } }
export const useOrchard = defineStore('orchard', () => {
  const server = ref<string>(uni.getStorageSync('bird-server') || defaultServer())
  const token = ref<string>(uni.getStorageSync('bird-session') || '')
  const state = ref<State | null>(null)
  const connection = ref('未连接')
  const error = ref('')
  const busy = ref(false)
  const now = ref(Date.now() / 1000)
  const offset = ref(0)
  let socket: UniApp.SocketTask | null = null
  let reconnect: ReturnType<typeof setTimeout> | null = null
  let poll: ReturnType<typeof setInterval> | null = null
  let clock: ReturnType<typeof setInterval> | null = null
  let visible = false, generation = 0, syncing = false
  const active = computed(() => state.value?.commands.find(c => ['pending', 'running'].includes(c.status)))

  function request<T>(path: string, method: 'GET' | 'POST' | 'PUT' = 'GET', data?: object): Promise<T> {
    const session = token.value
    return new Promise((resolve, reject) => {
      uni.request({ url: server.value.replace(/\/$/, '') + '/api' + path, method, data,
        header: { Authorization: 'Bearer ' + session, 'Content-Type': 'application/json' }, timeout: 12000,
        success: res => {
          if (res.statusCode >= 200 && res.statusCode < 300) return resolve(res.data as T)
          const detail = (res.data as { detail?: unknown })?.detail
          if (res.statusCode === 401 && path !== '/login' && session === token.value) clearSession()
          reject(new ApiError(typeof detail === 'string' ? detail : '请求参数不正确，请刷新后重试', res.statusCode))
        }, fail: () => reject(new ApiError('无法连接服务器，请检查地址和网络', 0)),
      })
    })
  }
  function accept(value: State) {
    if (state.value && value.server_time < state.value.server_time) return
    state.value = value
    offset.value = value.server_time - Date.now() / 1000
    error.value = ''
  }
  async function sync() {
    if (!token.value || syncing) return
    syncing = true
    const session = token.value
    try { const value = await request<State>('/state'); if (session === token.value) accept(value) }
    catch (e) { connection.value = '连接中断'; error.value = (e as Error).message }
    finally { syncing = false }
  }
  function connect() {
    if (!visible || !token.value || socket) return
    const version = generation
    connection.value = '连接中'
    socket = uni.connectSocket({ url: server.value.replace(/^http/, 'ws').replace(/\/$/, '') + '/api/ws', complete: () => {} })
    const current = socket
    current.onOpen(() => { if (version === generation) current.send({ data: JSON.stringify({ token: token.value }) }) })
    current.onMessage(message => {
      if (version !== generation) return
      try { accept(JSON.parse(String(message.data))); connection.value = '实时连接' } catch { /* Ignore incomplete transport messages. */ }
    })
    const lost = () => {
      if (version !== generation || current !== socket) return
      socket = null
      current.close({})
      connection.value = '重连中 · 查询补偿'
      if (visible && token.value) reconnect = setTimeout(connect, 2500)
    }
    current.onClose(lost)
    current.onError(lost)
  }
  function suspend() {
    visible = false; generation++
    if (reconnect) clearTimeout(reconnect)
    if (poll) clearInterval(poll)
    if (clock) clearInterval(clock)
    reconnect = poll = clock = null
    socket?.close({}); socket = null
  }
  function resume() {
    suspend(); visible = true
    now.value = Date.now() / 1000 + offset.value
    if (!token.value) return
    void sync(); connect()
    poll = setInterval(() => { void sync() }, 5000)
    clock = setInterval(() => { now.value = Date.now() / 1000 + offset.value }, 250)
  }
  function clearSession() {
    suspend(); token.value = ''; state.value = null; connection.value = '未登录'
    uni.removeStorageSync('bird-session')
    uni.removeStorageSync('bird-command-retry')
  }
  async function login(url: string, username: string, password: string) {
    if (!/^https?:\/\/[^/\s]+(?::\d+)?$/.test(url.replace(/\/$/, ''))) throw new Error('请输入完整服务地址，例如 http://192.168.1.10:8008')
    suspend(); server.value = url.replace(/\/$/, ''); uni.setStorageSync('bird-server', server.value)
    const result = await request<{ token: string }>('/login', 'POST', { username, password })
    token.value = result.token; uni.setStorageSync('bird-session', result.token); resume()
  }
  async function logout() {
    try { await request('/logout', 'POST') }
    finally { clearSession() }
  }
  async function mutate(path: string, method: 'POST' | 'PUT' = 'POST', data?: object) {
    const result = await request(path, method, data); await sync(); return result
  }
  async function command(duration: number, alarm_id: string | null) {
    const signature = JSON.stringify({ duration, alarm_id })
    let saved = uni.getStorageSync('bird-command-retry') as { signature: string; request_id: string } | undefined
    if (!saved || saved.signature !== signature) {
      saved = { signature, request_id: `req_${Date.now()}_${Math.random().toString(36).slice(2)}` }
      uni.setStorageSync('bird-command-retry', saved)
    }
    try {
      const result = await request<Command>('/commands', 'POST', { duration, alarm_id, request_id: saved.request_id })
      uni.removeStorageSync('bird-command-retry'); await sync(); return result
    } catch (e) {
      if ((e as ApiError).status) uni.removeStorageSync('bird-command-retry')
      throw e
    }
  }
  function media(path: string) { return server.value + '/api/' + path + '?ticket=' + encodeURIComponent(state.value?.media_ticket || '') }
  return { server, token, state, connection, error, busy, now, active, request, login, logout, mutate, command, media, sync, resume, suspend }
})
