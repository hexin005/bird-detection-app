<script setup lang="ts">
import { useHost, names, clock, shortTime, time, alarmClass } from '../host/hostContext'
import RecordsLogView from '../host/RecordsLogView.vue'
import VideoLibrary from '../VideoLibrary.vue'

const host = useHost()
</script>
<template>
  <view class="hd"><text class="b">检测日志</text><text class="s mono">LOG · {{ host.s?.counts.total || 0 }} TOTAL</text></view>
  <view class="qh-seg">
    <view class="qh-seg__item" :class="{ 'is-active': host.recordMode === 'actions' }" @click="host.recordMode = 'actions'">▍执行日志</view>
    <view class="qh-seg__item" :class="{ 'is-active': host.recordMode === 'videos' }" @click="host.recordMode = 'videos'">视频档案</view>
  </view>

  <template v-if="host.recordMode === 'actions'">
    <view class="board">
      <view class="board-hd"><text class="bt">最近班次</text><text class="be mono">RECENT FLIGHTS</text></view>
      <view class="cols mono"><text>班次</text><text>鸟种</text><text>时长</text><text>时刻</text><text style="text-align:right">状态</text></view>
      <view v-for="a in (host.s?.alarms || []).slice(0, 3)" :key="a.id" class="row" style="cursor:pointer" @click="host.openAlarm(a)">
        <text class="fno mono">BRD-{{ a.id.slice(-4).toUpperCase() }}</text>
        <view class="spn"><text class="sn">{{ a.species }} ×{{ a.count }}</text><text class="ss mono">置信度 {{ Math.round(a.confidence * 100) }}%</text></view>
        <text class="qty mono">{{ a.video_time.toFixed(1) }}s</text><text class="tm mono">{{ clock(a.at).slice(0, 5) }}</text>
        <view class="st"><text class="flap done mono">{{ names(a.status) }}</text></view>
      </view>
      <view v-if="!(host.s?.alarms || []).length" class="empty mono">NO ARCHIVES · 开始检测后生成</view>
    </view>
    <!-- 巡逻日志:指令链归并(共享组件) -->
    <RecordsLogView />
  </template>
  <VideoLibrary v-else :key="host.archiveNonce" :initial-task="host.archiveTask" :initial-time="host.archiveTime" />
</template>
<style scoped>
.hd{display:flex;justify-content:space-between;align-items:center;padding:14px 16px 10px}.hd .b{font-size:18px;letter-spacing:2px;color:var(--ink-900)}.hd .s{font-size:9px;color:var(--ink-400);letter-spacing:2px}
.board{margin:0 14px 10px;border:1px solid var(--line)}.board-hd{display:flex;justify-content:space-between;padding:8px 10px;border-bottom:1px solid var(--line);background:var(--surface-card)}.board-hd .bt{font-size:11px;letter-spacing:3px;color:var(--ink-900);font-weight:800}.board-hd .be{font-size:9px;color:var(--ink-400);letter-spacing:2px}
.cols{display:grid;grid-template-columns:64px 1fr 34px 44px 58px;padding:5px 10px;font-size:9px;letter-spacing:2px;color:var(--ink-400);border-bottom:1px solid var(--line)}
.row{display:grid;grid-template-columns:64px 1fr 34px 44px 58px;align-items:center;padding:0 10px;border-bottom:1px solid rgba(42,49,60,.55)}.row .fl{padding:7px 0}
.fno{font-size:11px;font-weight:700;color:var(--accent);letter-spacing:1px}
.spn{display:flex;flex-direction:column;gap:1px;min-width:0}.sn{font-size:13px;font-weight:700;color:var(--ink-900)}.ss{font-size:8.5px;color:var(--ink-400)}
.qty{font-size:14px;color:var(--ink-900)}.tm{font-size:11px;color:var(--ink-500)}.st{justify-self:end}
.flap{display:inline-block;min-width:52px;text-align:center;font-size:10px;font-weight:800;letter-spacing:2px;padding:4px 0 3px;position:relative}
.flap::after{content:'';position:absolute;left:0;right:0;top:50%;height:1px;background:rgba(0,0,0,.45)}
.flap.done{background:#171c24;color:var(--ink-400);border:1px solid var(--line)}
.empty{padding:18px;text-align:center;font-size:10px;letter-spacing:2px;color:var(--ink-400)}
</style>
