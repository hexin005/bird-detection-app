// 视频工作区控制器:已选视频/上传/启停/播放路径,模块级单例。
// 主题壳切换时组件会重建,但这里的响应式状态与进行中的上传/请求不受影响。
import { computed, ref } from 'vue'
import type { useOrchard } from '../../store'

type Store = ReturnType<typeof useOrchard>
type VideoItem = { id: string; name: string; duration: number }

const selected = ref<VideoItem | null>(null)
const uploading = ref(false)
const percent = ref(0)
const error = ref('')
let initialized = false
let picker: HTMLInputElement | null = null

export function useWorkspace(store: Store) {
  /** H5 文件选择器清理(组件卸载时调用) */
  function destroyPicker() { picker?.remove(); picker = null }
  /** 拉取服务端视频列表并预选最新一条(整个会话只拉一次;换账号由 reset 重置) */
  async function init() {
    if (initialized) return
    initialized = true
    try {
      const result = await store.request<{ items: VideoItem[] }>('/videos')
      selected.value = result.items[0] || null
    } catch { /* 连接横幅负责展示故障 */ }
  }
  /** 会话级重置(登出/换账号) */
  function reset() {
    initialized = false
    selected.value = null; uploading.value = false; percent.value = 0; error.value = ''
  }
  function choose() {
    // #ifdef H5
    const input = document.createElement('input')
    input.type = 'file'; input.accept = '.mp4,.mov,.avi,.webm,.mkv,video/*'
    picker?.remove(); picker = input
    input.style.display = 'none'; document.body.appendChild(input)
    input.onchange = () => {
      const file = input.files?.[0]
      input.remove(); picker = null
      if (!file) return
      if (file.size > 500 * 1024 * 1024) { error.value = '请选择 500 MB 以内的视频'; return }
      uploading.value = true; percent.value = 0; error.value = ''
      const xhr = new XMLHttpRequest()
      xhr.open('POST', store.server + '/api/videos'); xhr.timeout = 300000
      xhr.setRequestHeader('Authorization', 'Bearer ' + store.token)
      xhr.setRequestHeader('X-Filename', encodeURIComponent(file.name))
      xhr.setRequestHeader('Content-Type', 'application/octet-stream')
      xhr.upload.onprogress = event => { if (event.lengthComputable) percent.value = Math.round(event.loaded / event.total * 100) }
      xhr.onload = () => {
        uploading.value = false
        try {
          const result = JSON.parse(xhr.responseText)
          if (xhr.status !== 200) throw new Error(result.detail)
          selected.value = result
        } catch (e) { error.value = (e as Error).message || '上传失败' }
      }
      xhr.onerror = xhr.ontimeout = () => { uploading.value = false; error.value = '上传中断，请检查网络后重试' }
      xhr.send(file)
    }
    document.body.appendChild(input)
    input.click()
    // #endif
  }
  async function start() {
    store.busy = true; error.value = ''
    try { await store.mutate('/monitor/start', 'POST', { video_id: selected.value?.id || null }) }
    catch (e) { error.value = (e as Error).message }
    finally { store.busy = false }
  }
  async function stop() {
    try { await store.mutate('/monitor/stop') }
    catch (e) { error.value = (e as Error).message }
  }

  const monitor = computed(() => store.state?.monitor)
  const running = computed(() => ['starting', 'running', 'stopping'].includes(monitor.value?.status || ''))
  const sameVideo = computed(() => !selected.value || !monitor.value?.video_id || selected.value.id === monitor.value.video_id)
  const path = computed(() =>
    sameVideo.value && monitor.value?.task_id && (monitor.value.stream_ready || monitor.value.result_ready)
      ? `media/${monitor.value.task_id}/${monitor.value.result_ready ? 'result.mp4' : 'index.m3u8'}`
      : '')

  return { selected, uploading, percent, error, monitor, running, sameVideo, path, init, reset, choose, start, stop, destroyPicker }
}
