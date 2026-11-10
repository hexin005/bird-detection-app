<script setup lang="ts">
// B 主题记录页(R1 巡逻日志):统计条 + 日志/档案双段;日志视图为共享 RecordsLogView。
// 筛选/回看任务由 Host 持有(切主题保留)。
import { useHost } from '../hostContext'
import VideoLibrary from '../../VideoLibrary.vue'
import RecordsLogView from '../RecordsLogView.vue'

const host = useHost()
</script>

<template>
  <view class="qh-header__brand">
    <text class="qh-page-title">检测档案</text>
    <text class="qh-page-subtitle">指令链自动归并 · 按日回溯</text>
  </view>
  <view class="rec-stats">
    <view class="rec-stat"><text class="n">{{ host.todayAlarms }}</text><text class="l">今日事件</text></view>
    <view class="rec-stat"><text class="n">{{ host.s?.counts.total || 0 }}</text><text class="l">检测累计</text></view>
    <view class="rec-stat"><text class="n">{{ host.s?.counts.completed || 0 }}</text><text class="l">驱离完成</text></view>
  </view>
  <view class="qh-seg">
    <view class="qh-seg__item" :class="{ 'is-active': host.recordMode === 'actions' }" @click="host.recordMode = 'actions'">▍巡逻日志</view>
    <view class="qh-seg__item" :class="{ 'is-active': host.recordMode === 'videos' }" @click="host.recordMode = 'videos'">视频档案</view>
  </view>

  <RecordsLogView v-if="host.recordMode === 'actions'" />
  <VideoLibrary v-else :key="host.archiveNonce" :initial-task="host.archiveTask" :initial-time="host.archiveTime" />
</template>

<style scoped>
/* 统计条:三格合并横排 */
.rec-stats{display:flex;margin:6px 14px 12px;border:2px solid var(--ink-900);background:var(--surface-card);box-shadow:4px 4px 0 var(--shadow-ink)}
.rec-stat{flex:1;text-align:center;padding:9px 0 7px;border-right:1px solid var(--line)}
.rec-stat:last-child{border-right:none}
.rec-stat .n{display:block;font-size:19px;font-weight:800;font-family:var(--font-num);line-height:1.1}
.rec-stat .l{display:block;font-size:10px;color:var(--ink-400);letter-spacing:2px;margin-top:2px}
</style>
