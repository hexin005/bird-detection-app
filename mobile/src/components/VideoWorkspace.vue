<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useOrchard } from '../store'
import VideoPlayer from './VideoPlayer.vue'
const store = useOrchard()
const selected = ref<{id:string;name:string;duration:number} | null>(null)
const uploading = ref(false), percent = ref(0), error = ref('')
let picker: HTMLInputElement | null = null
const m = computed(() => store.state?.monitor)
const running = computed(() => ['starting','running','stopping'].includes(m.value?.status || ''))
const task = computed(() => m.value?.task_id)
const sameVideo = computed(() => !selected.value || !m.value?.video_id || selected.value.id===m.value.video_id)
const path = computed(() => sameVideo.value && task.value && (m.value?.stream_ready || m.value?.result_ready) ? `media/${task.value}/${m.value.result_ready ? 'result.mp4' : 'index.m3u8'}` : '')
function choose() {
  const input = document.createElement('input'); input.type = 'file'; input.accept = '.mp4,.mov,.avi,.webm,.mkv,video/*'
  picker?.remove(); picker = input; input.style.display = 'none'; document.body.appendChild(input)
  input.onchange = () => {
    const file = input.files?.[0]
    if (!file) return
    if (file.size > 500*1024*1024) { error.value = '请选择 500 MB 以内的视频'; return }
    uploading.value = true; percent.value = 0; error.value = ''
    const xhr = new XMLHttpRequest()
    xhr.open('POST', store.server + '/api/videos'); xhr.timeout = 300000
    xhr.setRequestHeader('Authorization','Bearer '+store.token)
    xhr.setRequestHeader('X-Filename',encodeURIComponent(file.name))
    xhr.setRequestHeader('Content-Type','application/octet-stream')
    xhr.upload.onprogress = event => { if (event.lengthComputable) percent.value = Math.round(event.loaded/event.total*100) }
    xhr.onload = () => { uploading.value = false; try { const result = JSON.parse(xhr.responseText); if (xhr.status!==200) throw new Error(result.detail); selected.value = result } catch(e) { error.value = (e as Error).message || '上传失败' } }
    xhr.onerror = xhr.ontimeout = () => { uploading.value = false; error.value = '上传中断，请检查网络后重试' }
    xhr.send(file)
  }
  input.click()
}
async function start() {
  store.busy = true; error.value = ''
  try { await store.mutate('/monitor/start','POST',{video_id:selected.value?.id || null}) }
  catch(e) { error.value = (e as Error).message }
  finally { store.busy = false }
}
async function stop() { try { await store.mutate('/monitor/stop') } catch(e) { error.value=(e as Error).message } }
onMounted(async () => { try { const result = await store.request<{items:{id:string;name:string;duration:number}[]}>('/videos'); selected.value = result.items[0] || null } catch { /* Main connection banner reports outages. */ } })
onBeforeUnmount(() => { picker?.remove() })
</script>
<template>
  <VideoPlayer v-if="path" :path="path" :autoplay="running"/>
  <view v-else class="video-placeholder"><text class="video-symbol">▷</text><text>{{ running ? '正在准备检测视频…' : '导入视频，开始一次鸟类巡护' }}</text><text class="small">{{ running ? '首段生成后即可播放，进度会持续更新' : '支持 MP4 / MOV / AVI / WebM，最大 500 MB' }}</text></view>
  <view class="source-bar"><view class="grow"><text class="card-title">{{ selected?.name || '使用服务器演示录像' }}</text><text class="small">{{ selected ? `时长 ${selected.duration.toFixed(1)} 秒` : '也可以选择自己的本地视频' }}</text></view><button class="secondary" :disabled="running || uploading || store.busy" @click="choose">选择视频</button></view>
  <view v-if="uploading"><text class="small">{{ percent===100 ? '上传完成，正在校验视频…' : `正在上传 ${percent}%` }}</text><progress :percent="percent" activeColor="#355c43" stroke-width="5"/></view>
  <text v-if="error" class="upload-error">{{ error }}</text>
  <view class="monitor-actions"><text class="small">{{ sameVideo ? m?.message : '视频已就绪，点击开始检测' }}{{ running ? ` · ${Math.floor(m?.progress || 0)}%` : '' }}</text><button :class="running?'secondary':'primary'" :disabled="uploading || store.busy || m?.status==='stopping'" @click="running?stop():start()">{{ running?'停止分析':'开始检测' }}</button></view>
  <progress v-if="running" :percent="m?.progress || 0" activeColor="#355c43" stroke-width="5"/>
  <view v-if="sameVideo && m?.result_ready && task" class="archive-hint"><text>本次结果已归档，可在记录中回看。</text><a :href="store.media(`media/${task}/result.mp4`)+'&download=true'">下载结果视频 ↓</a></view>
  <text class="note">录像分析 · 原帧率播放，模型按采样帧识别；框在两次采样之间短暂保留。完成后自动保存到服务器电脑，支持下载。</text>
</template>
<style scoped></style>
