<script setup lang="ts">
import { useHost, names, clock, shortTime, time, alarmClass } from '../host/hostContext'

const host = useHost()
</script>
<template>
  <view style="padding:12px"><b style="font-size:16px;color:#10130c">! 告警列表</b><span style="font-size:10px;color:#4a5a3e;margin-left:8px">{{ host.s?.counts.pending || 0 }} 条待处理</span></view>
  <view v-for="a in host.pending.slice(0, 6)" :key="a.id" class="dlg" style="cursor:pointer" @click="host.openAlarm(a)">
    <view class="who mono">告警 No.{{ a.id.slice(-4) }} · {{ shortTime(a.at) }}</view>
    <p class="txt">野生的<text class="hl">{{ a.species }} ×{{ a.count }}</text> 出现在东南果树区!<text class="hl">{{ Math.round(a.confidence * 100) }}%</text> 置信度 · 已录像。</p>
    <view class="ch"><span class="c go">▶ {{ host.mode === 'acoustic' ? '声波驱离' : host.mode === 'infrared' ? '红外驱离' : '双模驱离' }}</span><span class="c">忽略</span></view>
    <span class="arrow">▼</span>
  </view>
  <view v-if="!host.pending.length" class="dlg"><p class="txt">果园平静…暂无待处理告警。开始观测后,告警会在这里出现。</p></view>
</template>
<style scoped>
.dlg{background:#10130c;border:4px solid #f4f1e4;box-shadow:0 0 0 4px #10130c,0 6px 0 rgba(0,0,0,.45);padding:12px 13px;position:relative}
.who{color:#f8d94a;font-size:10px;font-weight:800;letter-spacing:2px;margin-bottom:5px;font-family:var(--font-num)}
.txt{color:#f4f1e4;font-size:13px;font-weight:700;line-height:1.7}
.hl{color:#8fe08f}
.ch{display:flex;gap:6px;margin-top:9px}
.c{flex:1;border:2px solid #f4f1e4;color:#f4f1e4;font-size:11px;font-weight:800;text-align:center;padding:6px 0}
.c.go{background:#f4f1e4;color:#10130c}
.arrow{position:absolute;right:10px;bottom:6px;color:#f4f1e4;font-size:12px;animation:qhBlink 1s steps(2) infinite}
</style>