<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useOrchard } from '../store'
import type { Frame } from '../types'
const store = useOrchard()
const shown = ref<Frame | null>(null)
const failed = ref(false)
const frame = computed(() => store.state?.monitor.frame)
const stale = computed(() => !!shown.value && store.now - shown.value.at > 5)
watch(() => store.state?.monitor.task_id, () => { shown.value = null; failed.value = false })
function loaded(value: Frame) { shown.value = value; failed.value = false }
</script>
<template>
  <view class="qh-video">
    <text class="qh-video__tag qh-video__tag--tl">录像演示 · YOLOv8</text>
    <template v-for="candidate in frame ? [frame] : []" :key="candidate.key">
      <image :src="store.media('frame/' + candidate.key + '.jpg')" mode="aspectFit" style="position:absolute;inset:0;width:100%;height:100%" @load="loaded(candidate)" @error="failed = true" />
    </template>
    <view v-if="!frame" style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px">
      <text style="font-size:26px;color:var(--brand-400)">◎</text>
      <text style="font-size:var(--text-sm);color:#c8d2bd">开始监测后显示真实识别画面</text>
    </view>
    <view v-else class="qh-scanline"/>
    <text class="qh-video__tag" style="top:12px;right:12px;left:auto">{{ stale ? '最后画面 · 已过期' : ['running','starting'].includes(store.state?.monitor.status || '') ? '监测中' : '最后检测画面' }}</text>
    <text class="qh-video__tag qh-video__tag--bl">
      <text v-if="failed">画面加载失败，等待重连</text>
      <text v-else-if="shown">视频 {{ shown.video_time.toFixed(1) }}s / {{ shown.duration.toFixed(0) }}s · 第 {{ shown.frame_id }} 帧</text>
      <text v-else>模型已配置 · 等待画面</text>
    </text>
  </view>
</template>
