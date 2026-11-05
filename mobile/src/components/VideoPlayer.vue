<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import Hls from 'hls.js'
import { useOrchard } from '../store'
const props = defineProps<{ path: string; seek?: number; autoplay?: boolean }>()
const store = useOrchard()
const host = ref<unknown>(null), message = ref('正在缓冲检测视频…')
let video: HTMLVideoElement | null = null, hls: Hls | null = null
let loadedPath = '', restoreTime = 0, resumePlayback = false
function seek() { if (video && Number.isFinite(props.seek)) video.currentTime = Math.max(0, props.seek || 0) }
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
  video.style.cssText = 'width:100%;height:100%;display:block;background:#1f382c;object-fit:contain'
  element?.appendChild(video)
  video.addEventListener('canplay', () => { message.value = ''; if (props.autoplay || resumePlayback) void video?.play().catch(() => {}) })
  video.addEventListener('loadedmetadata', () => { if (video) video.currentTime = restoreTime })
  video.addEventListener('error', () => { message.value = '视频暂不可播放，请重新加载' })
  load()
})
watch(() => props.path, load)
watch(() => props.seek, seek)
onBeforeUnmount(() => { hls?.destroy(); if (video) { video.pause(); video.removeAttribute('src'); video.load(); video.remove() } })
</script>
<template><view class="video-player"><view ref="host" class="video-host"/><view v-if="message" class="video-message" @click="load">{{ message }}</view></view></template>
<style scoped>
.video-player {
  position: relative;
  background: var(--brand-900);
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: var(--shadow-md);
}
.video-host {
  height: 260px;
}
.video-message {
  position: absolute;
  top: var(--space-4);
  left: var(--space-4);
  right: var(--space-4);
  font-size: var(--text-sm);
  color: #fff;
  background: rgba(32, 56, 45, 0.74);
  backdrop-filter: blur(4px);
  border-radius: var(--radius-xs);
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
}
</style>
