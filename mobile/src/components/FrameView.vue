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
  <view class="camera">
    <view v-if="!frame" class="camera-empty"><text class="camera-symbol">◎</text><text>东区 · 01 号监控点</text><text class="small">开始监测后显示真实识别画面</text></view>
    <template v-for="candidate in frame ? [frame] : []" :key="candidate.key">
      <image class="camera-image" :src="store.media('frame/' + candidate.key + '.jpg')" mode="aspectFit" @load="loaded(candidate)" @error="failed = true" />
    </template>
    <view class="camera-top"><text class="camera-tag">录像演示 · YOLOv8</text><text>{{ stale ? '最后画面 · 已过期' : ['running','starting'].includes(store.state?.monitor.status || '') ? '监测中' : '最后检测画面' }}</text></view>
    <view class="camera-caption"><text v-if="failed">画面加载失败，等待重连</text><text v-else-if="shown">视频 {{ shown.video_time.toFixed(1) }}s / {{ shown.duration.toFixed(0) }}s · 第 {{ shown.frame_id }} 帧</text><text v-else>模型已配置 · 等待画面</text></view>
  </view>
  <view v-if="shown && !failed" class="frame-meta"><text>本帧 {{ shown.count }} 只 · 推理 {{ shown.inference_ms }}ms</text><text>{{ shown.detections.map(d => `${d.species} ${(d.confidence * 100).toFixed(0)}%`).join(' / ') || '未检出鸟类' }}</text></view>
</template>
