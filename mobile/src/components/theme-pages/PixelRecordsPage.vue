<script setup lang="ts">
import { useHost, names, clock, shortTime, time, alarmClass } from '../host/hostContext'

const host = useHost()
</script>
<template>
  <view style="padding:12px"><b style="font-size:16px;color:#10130c">📖 观测图鉴</b><span style="font-size:10px;color:#4a5a3e;margin-left:8px">{{ (host.s?.alarms || []).length }} 条</span></view>
  <view v-for="a in (host.s?.alarms || []).slice(0, 8)" :key="a.id" class="dlg" style="cursor:pointer" @click="host.openAlarm(a)">
    <view class="who mono">{{ shortTime(a.at) }} · {{ a.species }}</view>
    <p class="txt">{{ a.species }} ×{{ a.count }} · 置信度 <text class="hl">{{ Math.round(a.confidence * 100) }}%</text></p>
  </view>
  <view v-if="!(host.s?.alarms || []).length" class="dlg"><p class="txt">暂无观测记录 — 开始检测后自动生成图鉴。</p></view>
</template>
<style scoped>
.dlg{background:#10130c;border:4px solid #f4f1e4;box-shadow:0 0 0 4px #10130c,0 6px 0 rgba(0,0,0,.45);padding:12px 13px;position:relative}
.who{color:#f8d94a;font-size:10px;font-weight:800;letter-spacing:2px;margin-bottom:5px;font-family:var(--font-num)}
.txt{color:#f4f1e4;font-size:12px;font-weight:700;line-height:1.6}
.hl{color:#8fe08f}
</style>