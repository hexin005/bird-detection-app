// AI 助手前端状态:模块级 reactive,小窗/整页/按钮三态切换与页面切换均不丢会话。
// 流式读取用 fetch + ReadableStream(MeHome 头像上传同款绕过 uni.request 的 H5 原生路径),
// SSE 解析必须按"缓冲区 + 事件边界"处理:网络分块与事件边界不对齐(评审④)。
// 图片提问:附件单张存 pendingImageFile,发送走 chat-image 原始字节(后端免 multipart),解析与文本共用。
import { reactive } from 'vue'
import type { AssistantRef, ChatMsg } from '../types'

export type AssistantConn = { server: string; token: string }

type SsePayload = { type: 'meta' | 'delta' | 'done' | 'error'; text?: string; refs?: AssistantRef[]; detail?: string }

export const IMAGE_MAX_BYTES = 8 * 1024 * 1024

export const assistantState = reactive({
  msgs: [] as ChatMsg[],
  busy: false,
  draft: '',
  configured: null as boolean | null, // null=状态未知(检查失败),允许尝试,成败由后端裁决
  abort: null as (() => void) | null,
  pendingImage: '' as string, // 已选图片 dataURL 预览;空串=未选
  pendingImageFile: null as File | null,
})

/** 纯函数:增量 SSE 解析。chunk 与事件边界不对齐时,残片留缓冲等待下一块;坏事件丢弃。 */
export function parseSseChunk(buffer: string, chunk: string): { events: string[]; buffer: string } {
  const text = buffer + chunk
  const parts = text.split('\n\n')
  const buffer2 = parts.pop() || ''
  return { events: parts, buffer: buffer2 }
}

function applyPayload(msg: ChatMsg, payload: SsePayload) {
  if (payload.type === 'meta') {
    msg.refs = payload.refs || []
    msg.phase = 'think' // 检索完成(参考资料已定),进入生成阶段
  } else if (payload.type === 'delta') {
    msg.phase = undefined
    msg.text += payload.text || ''
  } else if (payload.type === 'done') {
    msg.streaming = false
  } else if (payload.type === 'error') {
    msg.phase = undefined
    msg.error = true
    msg.text += (msg.text ? '\n\n' : '') + '⚠ ' + (payload.detail || '回答中断')
  }
}

/** 选择图片:类型/大小校验后读 dataURL 作预览;校验失败 reject 文案给调用方 toast。 */
export function attachImage(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
      reject(new Error('仅支持 JPG / PNG / WebP 图片'))
      return
    }
    if (file.size > IMAGE_MAX_BYTES) {
      reject(new Error('图片不能超过 8 MB'))
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      assistantState.pendingImage = String(reader.result || '')
      assistantState.pendingImageFile = file
      resolve(assistantState.pendingImage)
    }
    reader.onerror = () => reject(new Error('图片读取失败'))
    reader.readAsDataURL(file)
  })
}

export function clearImage() {
  assistantState.pendingImage = ''
  assistantState.pendingImageFile = null
}

export async function checkAssistant(conn: AssistantConn) {
  try {
    const resp = await fetch(conn.server + '/api/assistant/status', { headers: { Authorization: 'Bearer ' + conn.token } })
    if (!resp.ok) throw new Error(String(resp.status))
    const data = await resp.json() as { configured?: boolean }
    assistantState.configured = !!data.configured
  } catch {
    assistantState.configured = null
  }
}

export function stopAssistant() {
  assistantState.abort?.()
}

/** SSE 消费统一入口:文本与图片提问共用;停止/中断/服务错误语义集中在此。 */
async function consumeStream(resp: Response, msg: ChatMsg, stopped: () => boolean) {
  const reader = resp.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    const parsed = parseSseChunk(buffer, decoder.decode(value, { stream: true }))
    buffer = parsed.buffer
    for (const raw of parsed.events) {
      const line = raw.trim()
      if (!line.startsWith('data:')) continue
      try {
        applyPayload(msg, JSON.parse(line.slice(5).trim()) as SsePayload)
      } catch { /* 单事件解析失败丢弃,不影响后续 */ }
    }
  }
  if (stopped()) {
    msg.stopped = true
  }
}

export async function askAssistant(question: string, conn: AssistantConn) {
  const q = question.trim()
  const img = assistantState.pendingImageFile
  if ((!q && !img) || assistantState.busy) return
  assistantState.msgs.push({ role: 'user', text: q || '（图片提问）', image: assistantState.pendingImage || undefined })
  assistantState.draft = ''
  clearImage()
  const msg = reactive<ChatMsg>({ role: 'assistant', text: '', streaming: true, phase: 'retrieve' })
  assistantState.msgs.push(msg)
  assistantState.busy = true
  const ctrl = new AbortController()
  assistantState.abort = () => ctrl.abort()
  let stopped = false
  ctrl.signal.addEventListener('abort', () => { stopped = true })
  try {
    let resp: Response
    if (img) {
      // 图片提问:原始字节上传(与头像上传同款免 multipart 约定),问题走 query;未输入时用默认追问
      const realQ = q || '这是什么鸟？该怎么处理？'
      resp = await fetch(`${conn.server}/api/assistant/chat-image?question=${encodeURIComponent(realQ)}`, {
        method: 'POST',
        headers: { 'Content-Type': img.type || 'image/jpeg', Authorization: 'Bearer ' + conn.token },
        body: img,
        signal: ctrl.signal,
      })
    } else {
      const history = assistantState.msgs
        .filter(m => !m.error && m.text)
        .slice(-7, -1)
        .map(m => ({ role: m.role, content: m.text.slice(0, 2000) }))
      resp = await fetch(conn.server + '/api/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + conn.token },
        body: JSON.stringify({ question: q, history }),
        signal: ctrl.signal,
      })
    }
    if (!resp.ok || !resp.body) {
      let detail = '服务异常 ' + resp.status
      try {
        const j = await resp.json() as { detail?: string }
        if (j?.detail) detail = j.detail
      } catch { /* 非 JSON 错误体,保留状态码文案 */ }
      throw new Error(detail)
    }
    await consumeStream(resp, msg, () => stopped)
  } catch (e) {
    if (stopped) {
      msg.stopped = true
      if (!msg.text) msg.text = '（已停止）'
    } else {
      msg.error = true
      msg.text += (msg.text ? '\n\n' : '') + '⚠ ' + (e instanceof Error ? e.message : '请求失败')
    }
  } finally {
    msg.streaming = false
    assistantState.busy = false
    assistantState.abort = null
  }
}

/** 登出/换账号时清空会话(hostContext.onTokenChange 调用) */
export function resetAssistant() {
  stopAssistant()
  assistantState.msgs = []
  assistantState.draft = ''
  assistantState.configured = null
  assistantState.busy = false
  clearImage()
}
