<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import Hls from 'hls.js'
import { useOrchard } from '../store'
const props = defineProps<{ path: string; seek?: number; autoplay?: boolean }>()
const store = useOrchard()
const host = ref<unknown>(null), message = ref('正在缓冲检测视频…')
/** 视频技术参数，取自 <video> 元素元数据 */
const meta = ref({ w: 0, h: 0, fps: 0, frames: 0, current: 0, duration: 0 })
let video: HTMLVideoElement | null = null, hls: Hls | null = null
let loadedPath = '', restoreTime = 0, resumePlayback = false, ticker: ReturnType<typeof setInterval> | null = null

function seek() { if (video && Number.isFinite(props.seek)) video.currentTime = Math.max(0, props.seek || 0) }
function readMeta() {
  if (!video) return
  meta.value = {
    w: video.videoWidth || 0,
    h: video.videoHeight || 0,
    fps: meta.value.fps,
    frames: meta.value.frames,
    current: video.currentTime || 0,
    duration: Number.isFinite(video.duration) ? video.duration : 0
  }
}
function load() {
  if (!video || !props.path) return
  const sameTask = loadedPath.split('/')[1] === props.path.split('/')[1]
  restoreTime = sameTask ? video.currentTime : props.seek || 0
  resumePlayback = !video.paused
  loadedPath = props.path
  hls?.destroy(); hls = null; message.value = '正在缓冲检测视频…'
  if (props.path.endsWith('.m3u8') && Hls.isSupported()) {
    hls = new Hls({ startPosition: restoreTime, liveSyncDurationCount: 100000, xhrSetup(xhr, url) {
      const request = new URL(url, store.server)
      request.searchParams.set('ticket', store.state?.media_ticket || '')
      xhr.open('GET', request.toString(), true)
    } })
    hls.loadSource(store.media(props.path)); hls.attachMedia(video)
    hls.on(Hls.Events.ERROR, (_, data) => { if (data.fatal) message.value = '播放中断，请点击重新加载' })
  } else video.src = store.media(props.path)
}
onMounted(() => {
  const node = host.value as { $el?: HTMLElement } & HTMLElement
  const element = node?.$el || node
  video = document.createElement('video')
  video.controls = true; video.playsInline = true; video.muted = true; video.preload = 'auto'
  video.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;display:block;background:transparent;object-fit:cover'
  element?.appendChild(video)
  video.addEventListener('canplay', () => { message.value = ''; if (props.autoplay || resumePlayback) void video?.play().catch(() => {}) })
  video.addEventListener('loadedmetadata', () => {
    if (video) video.currentTime = restoreTime
    readMeta()
    // 帧率无法从 <video> 直接读取，按检测管线默认 30fps 估算总帧
    if (video && video.duration > 0 && !meta.value.fps) {
      meta.value.fps = 30
      meta.value.frames = Math.round(30 * video.duration)
    }
  })
  video.addEventListener('timeupdate', readMeta)
  video.addEventListener('error', () => { message.value = '视频暂不可播放，请重新加载' })
  load()
  ticker = setInterval(readMeta, 500)
})
watch(() => props.path, load)
watch(() => props.seek, seek)
onBeforeUnmount(() => {
  hls?.destroy()
  if (ticker) clearInterval(ticker)
  if (video) { video.pause(); video.removeAttribute('src'); video.load(); video.remove() }
})
</script>
<template>
  <view class="qh-video">
    <!-- 左上角：视频播放参数 -->
    <view class="qh-video__tag qh-video__tag--tl qh-video__meta">
      <text v-if="meta.w">{{ meta.w }}×{{ meta.h }}</text>
      <text v-if="meta.fps">· {{ meta.fps }}fps</text>
      <text v-if="meta.duration">· {{ meta.duration.toFixed(1) }}s</text>
    </view>
    <view ref="host" style="position:absolute;top:0;left:0;width:100%;height:100%"/>
    <text v-if="message" class="qh-video__tag" style="top:12px;left:50%;transform:translateX(-50%)" @click="load">{{ message }}</text>
    <!-- 左下角：当前播放进度 -->
    <view class="qh-video__tag qh-video__tag--bl">
      <text>{{ meta.current.toFixed(1) }}s / {{ meta.duration.toFixed(1) }}s</text>
    </view>
  </view>
</template>
