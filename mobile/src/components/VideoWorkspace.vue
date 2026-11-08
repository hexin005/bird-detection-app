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
onMounted(async () => { try { const result = await store.request<{items:{id:string;name:string;duration:number}[]}>('/videos'); selected.value = result.items[0] || null } catch { /* connection banner reports outages */ } })
onBeforeUnmount(() => { picker?.remove() })
</script>
<template>
  <view class="qh-window">
    <view class="qh-tbar"><view class="qh-tbar__box">×</view><text class="qh-tbar__t">监测 — CAM-01 (东区)</text></view>
    <view class="qh-window__bd">
      <VideoPlayer v-if="path" :path="path" :autoplay="running"/>
      <view v-else class="qh-video">
        <text class="qh-video__tag qh-video__tag--tl">录像演示 · YOLOv8</text>
        <view class="qh-scanline"/>
        <view class="qh-detect-box" style="left:50%;top:32%;width:34%;height:46%;opacity:.25"/>
        <text class="qh-video__tag qh-video__tag--bl">{{ running ? '正在准备检测视频…' : '导入视频，开始一次鸟类巡护' }}</text>
      </view>

      <view class="qh-srcrow">
        <view class="qh-srcrow__info">
          <text class="qh-srcrow__name">{{ selected?.name || '服务器演示录像' }}</text>
          <text class="qh-srcrow__dur">{{ selected ? `时长 ${selected.duration.toFixed(1)} 秒` : '支持 MP4 / MOV / AVI / WebM，最大 500 MB' }}</text>
        </view>
        <button class="qh-btn qh-btn--secondary" :disabled="running || uploading || store.busy" @click="choose">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1.5" y="3" width="9" height="10" rx="2" stroke="#111111" stroke-width="1.5"/><path d="M10.5 6.5l4-2.5v8l-4-2.5" stroke="#111111" stroke-width="1.5" stroke-linejoin="round"/></svg>选择视频
        </button>
      </view>

      <!-- 上传进度 -->
      <view v-if="uploading" class="qh-upload">
        <view class="qh-upload__top">
          <text class="qh-upload__label">{{ percent === 100 ? '上传完成，正在校验…' : '正在上传' }}</text>
          <text class="qh-upload__pct">{{ percent }}%</text>
        </view>
        <view class="qh-progress"><view class="qh-progress__bar" :style="{ width: percent + '%' }"/></view>
      </view>

      <view v-if="error" class="qh-card" style="background:var(--danger-bg);border-color:var(--danger-line)">
        <text style="font-size:var(--text-xs);color:var(--danger-fg)">{{ error }}</text>
      </view>

      <button class="qh-btn qh-btn--primary" :disabled="uploading || store.busy || m?.status === 'stopping'" @click="running ? stop() : start()">
        <svg v-if="!running" width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3.5 2.2v9.6c0 .8.9 1.3 1.6.9l7.3-4.8c.6-.4.6-1.4 0-1.8L5.1 1.3c-.7-.4-1.6.1-1.6.9z" fill="#f4f4f0"/></svg>
        {{ running ? '停止分析' : '开始检测' }}
      </button>

      <!-- 检测进度 -->
      <view v-if="running" class="qh-upload">
        <view class="qh-upload__top">
          <text class="qh-upload__label">{{ m?.message || '正在分析录像' }}</text>
          <text class="qh-upload__pct">{{ Math.floor(m?.progress || 0) }}%</text>
        </view>
        <view class="qh-progress"><view class="qh-progress__bar" :style="{ width: (m?.progress || 0) + '%' }"/></view>
      </view>

      <view v-if="sameVideo && m?.result_ready && task" class="qh-archive">
        <text class="qh-archive__text">本次结果已归档，可在记录中回看</text>
        <text class="qh-link">
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M6.5 1.5v7M3.5 5.8l3 3 3-3M1.8 11h9.4" stroke="#111111" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <a :href="store.media(`media/${task}/result.mp4`)+'&download=true'" style="color:inherit">下载结果视频</a>
        </text>
      </view>

      <text class="qh-hint" style="display:block;text-align:left">{{ sameVideo ? (m?.message || '') : '视频已就绪，点击开始检测' }}</text>
    </view>
  </view>
</template>
