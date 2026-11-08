<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { useOrchard } from '../store'
import VideoPlayer from './VideoPlayer.vue'
import { useWorkspace } from './host/useWorkspace'

const store = useOrchard()
// 状态与动作来自共享工作区控制器:主题壳切换时上传/选中/错误不丢失
const ws = useWorkspace(store)
onMounted(() => { void ws.init().catch(() => { /* 连接横幅负责展示故障 */ }) })
onBeforeUnmount(() => ws.destroyPicker())
</script>
<template>
  <VideoPlayer v-if="ws.path.value" :path="ws.path.value" :autoplay="ws.running.value" />
  <view v-else class="qh-video">
    <text class="qh-video__tag qh-video__tag--tl">录像演示 · YOLOv8</text>
    <view class="qh-scanline"/>
    <view class="qh-detect-box" style="left:50%;top:32%;width:34%;height:46%;opacity:.25"/>
    <text class="qh-video__tag qh-video__tag--bl">{{ ws.running.value ? '正在准备检测视频…' : '导入视频，开始一次鸟类巡护' }}</text>
  </view>

  <view class="qh-srcrow">
    <view class="qh-srcrow__info">
      <text class="qh-srcrow__name">{{ ws.selected.value?.name || '服务器演示录像' }}</text>
      <text class="qh-srcrow__dur">{{ ws.selected.value ? `时长 ${ws.selected.value.duration.toFixed(1)} 秒` : '支持 MP4 / MOV / AVI / WebM，最大 500 MB' }}</text>
    </view>
    <button class="qh-btn qh-btn--secondary" :disabled="ws.running.value || ws.uploading.value || store.busy" @click="ws.choose">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1.5" y="3" width="9" height="10" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M10.5 6.5l4-2.5v8l-4-2.5" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>选择视频
    </button>
  </view>

  <!-- 上传进度 -->
  <view v-if="ws.uploading.value" class="qh-upload">
    <view class="qh-upload__top">
      <text class="qh-upload__label">{{ ws.percent.value === 100 ? '上传完成，正在校验…' : '正在上传' }}</text>
      <text class="qh-upload__pct">{{ ws.percent.value }}%</text>
    </view>
    <view class="qh-progress"><view class="qh-progress__bar" :style="{ width: ws.percent.value + '%' }"/></view>
  </view>

  <view v-if="ws.error.value" class="qh-card" style="background:var(--danger-bg);border-color:var(--danger-line)">
    <text style="font-size:var(--text-xs);color:var(--danger-fg)">{{ ws.error.value }}</text>
  </view>

  <button class="qh-btn qh-btn--primary" :disabled="ws.uploading.value || store.busy || ws.monitor.value?.status === 'stopping'" @click="ws.running.value ? ws.stop() : ws.start()">
    <svg v-if="!ws.running.value" width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3.5 2.2v9.6c0 .8.9 1.3 1.6.9l7.3-4.8c.6-.4.6-1.4 0-1.8L5.1 1.3c-.7-.4-1.6.1-1.6.9z" fill="currentColor"/></svg>
    {{ ws.running.value ? '停止分析' : '开始检测' }}
  </button>

  <!-- 检测进度 -->
  <view v-if="ws.running.value" class="qh-upload">
    <view class="qh-upload__top">
      <text class="qh-upload__label">{{ ws.monitor.value?.message || '正在分析录像' }}</text>
      <text class="qh-upload__pct">{{ Math.floor(ws.monitor.value?.progress || 0) }}%</text>
    </view>
    <view class="qh-progress"><view class="qh-progress__bar" :style="{ width: (ws.monitor.value?.progress || 0) + '%' }"/></view>
  </view>

  <view v-if="ws.sameVideo.value && ws.monitor.value?.result_ready && ws.monitor.value?.task_id" class="qh-archive">
    <text class="qh-archive__text">本次结果已归档，可在记录中回看</text>
    <text class="qh-link">
      <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M6.5 1.5v7M3.5 5.8l3 3 3-3M1.8 11h9.4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <a :href="store.media(`media/${ws.monitor.value!.task_id}/result.mp4`)+'&download=true'" style="color:inherit">下载结果视频</a>
    </text>
  </view>

  <text class="qh-hint" style="display:block;text-align:left">{{ ws.sameVideo.value ? (ws.monitor.value?.message || '') : '视频已就绪，点击开始检测' }}</text>
</template>
