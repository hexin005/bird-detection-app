<script setup lang="ts">
import { useHost, names, clock, shortTime, time, alarmClass } from '../host/hostContext'
import RecordsLogView from '../host/RecordsLogView.vue'
import VideoLibrary from '../VideoLibrary.vue'

const host = useHost()
</script>
<template>
  <view class="hd"><text class="b">观测档案</text><text class="s">执行日志 · 视频回看 · 物种索引</text></view>
  <view class="qh-seg">
    <view class="qh-seg__item" :class="{ 'is-active': host.recordMode === 'actions' }" @click="host.recordMode = 'actions'">▍执行日志</view>
    <view class="qh-seg__item" :class="{ 'is-active': host.recordMode === 'videos' }" @click="host.recordMode = 'videos'">视频档案</view>
  </view>

  <template v-if="host.recordMode === 'actions'">
    <view class="hd" style="padding-top:2px"><text class="b" style="font-size:13px">最近观测</text><text class="s">点击看详情</text></view>
    <view v-for="a in (host.s?.alarms || []).slice(0, 3)" :key="a.id" class="arc" style="cursor:pointer" @click="host.openAlarm(a)">
      <i class="play">▶</i>
      <view class="info"><text class="nm">{{ a.species }} · 检测片段</text><text class="meta mono">{{ shortTime(a.at) }} · {{ a.video_time.toFixed(1) }}s · {{ Math.round(a.confidence * 100) }}%</text></view>
      <text class="st">{{ names(a.status) }}</text>
    </view>
    <view v-if="!(host.s?.alarms || []).length" class="empty">暂无检测档案</view>
    <!-- 巡逻日志:指令链归并(共享组件) -->
    <RecordsLogView />
    <view class="hd" style="margin-top:8px"><text class="b" style="font-size:13px">物种索引</text><text class="s">自动建立</text></view>
    <view style="display:flex;flex-wrap:wrap;gap:6px;padding:0 16px 14px">
      <text v-for="sp in [...new Set((host.s?.alarms || []).map(a => a.species))]" :key="sp" class="sp-tag">{{ sp }}</text>
    </view>
  </template>
  <VideoLibrary v-else :key="host.archiveNonce" :initial-task="host.archiveTask" :initial-time="host.archiveTime" />
</template>
<style scoped>
.hd{display:flex;justify-content:space-between;align-items:center;padding:14px 16px 10px}.hd .b{font-size:16px;font-weight:900;letter-spacing:2px;color:var(--ink-900)}.hd .s{font-size:9px;color:var(--ink-400)}
.arc{display:flex;align-items:center;gap:10px;margin:0 16px 10px;border:2px solid #191919;background:#fbfaf4;box-shadow:3px 4px 0 rgba(25,25,25,.22);padding:10px;cursor:pointer}
.play{width:36px;height:36px;flex-shrink:0;border:2px solid #191919;display:flex;align-items:center;justify-content:center;font-size:14px;font-style:normal}
.info{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.nm{font-size:12px;font-weight:900}
.meta{font-size:9px;color:var(--ink-400)}
.st{font-size:9px;font-weight:900;border:2px solid #191919;padding:2px 6px;color:#191919;flex-shrink:0}
.empty{text-align:center;padding:20px;font-size:10px;color:var(--ink-400)}
.sp-tag{border:1px solid #191919;font-size:10px;padding:2px 6px;color:#191919}
</style>
