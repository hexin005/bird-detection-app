<script setup lang="ts">
import { useHost, names, clock, shortTime, time, alarmClass } from '../host/hostContext'
import RecordsLogView from '../host/RecordsLogView.vue'
import VideoLibrary from '../VideoLibrary.vue'

const host = useHost()
</script>
<template>
  <view style="padding:12px"><b style="font-size:16px;color:#10130c">📖 观测图鉴</b><span style="font-size:10px;color:#4a5a3e;margin-left:8px">{{ (host.s?.alarms || []).length }} 条 · 物种 {{ [...new Set((host.s?.alarms || []).map(a => a.species))].length }}</span></view>
  <view class="qh-seg">
    <view class="qh-seg__item" :class="{ 'is-active': host.recordMode === 'actions' }" @click="host.recordMode = 'actions'">▍执行日志</view>
    <view class="qh-seg__item" :class="{ 'is-active': host.recordMode === 'videos' }" @click="host.recordMode = 'videos'">视频档案</view>
  </view>

  <template v-if="host.recordMode === 'actions'">
    <view v-if="(host.s?.alarms || []).length" class="card">
      <b class="t">最近观测 · 点开详情</b>
      <view v-for="a in (host.s?.alarms || []).slice(0, 3)" :key="a.id" class="entry" style="cursor:pointer" @click="host.openAlarm(a)">
        <view class="info"><b>{{ a.species }} ×{{ a.count }}</b><span class="mono">{{ shortTime(a.at) }} · {{ Math.round(a.confidence * 100) }}%</span></view>
        <span class="st">{{ names(a.status) }}</span>
      </view>
    </view>
    <view v-else class="card"><p class="txt">暂无观测记录 — 开始检测后自动生成图鉴。</p></view>
    <!-- 巡逻日志:指令链归并(共享组件) -->
    <RecordsLogView />
  </template>
  <VideoLibrary v-else :key="host.archiveNonce" :initial-task="host.archiveTask" :initial-time="host.archiveTime" />
</template>
<style scoped>
.card{background:#10130c;border:4px solid #f4f1e4;box-shadow:0 0 0 4px #10130c,0 6px 0 rgba(0,0,0,.45);padding:12px 13px;margin:0 12px 12px;position:relative}
.t{color:#f8d94a;font-size:10px;font-weight:800;letter-spacing:2px;display:block;margin-bottom:8px}
.txt{color:#f4f1e4;font-size:12px;font-weight:700;line-height:1.6}
.entry{display:flex;gap:10px;align-items:center;padding:7px 0;border-bottom:1px solid #3a4130}
.entry:last-child{border-bottom:none}
.entry .info{flex:1;min-width:0}
.entry .info b{color:#f4f1e4;font-size:12px;display:block}
.entry .info span{color:#7f8a72;font-size:9px}
.st{font-size:9px;font-weight:800;border:2px solid #8fe08f;padding:2px 6px;color:#8fe08f;flex-shrink:0}
</style>
