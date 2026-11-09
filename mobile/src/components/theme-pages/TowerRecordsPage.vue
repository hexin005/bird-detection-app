<script setup lang="ts">
import { useHost, names, clock, shortTime, time, alarmClass } from '../host/hostContext'

const host = useHost()
</script>
<template>
  <view class="hd"><text class="b">检测日志</text><text class="s mono">LOG · {{ host.s?.counts.total || 0 }} TOTAL</text></view>
  <view class="board">
    <view class="board-hd"><text class="bt">检测档案</text><text class="be mono">ARCHIVES</text></view>
    <view class="cols mono"><text>班次</text><text>鸟种</text><text>时长</text><text>时刻</text><text style="text-align:right">状态</text></view>
    <view v-for="a in (host.s?.alarms || []).slice(0, 8)" :key="a.id" class="row" style="cursor:pointer" @click="host.openAlarm(a)">
      <text class="fno mono">BRD-{{ a.id.slice(-4).toUpperCase() }}</text>
      <view class="spn"><text class="sn">{{ a.species }} ×{{ a.count }}</text><text class="ss mono">置信度 {{ Math.round(a.confidence * 100) }}%</text></view>
      <text class="qty mono">{{ a.video_time.toFixed(1) }}s</text><text class="tm mono">{{ clock(a.at).slice(0, 5) }}</text>
      <view class="st"><text class="flap done mono">{{ names(a.status) }}</text></view>
    </view>
    <view v-if="!(host.s?.alarms || []).length" class="empty mono">NO ARCHIVES · 开始检测后生成</view>
  </view>
  <view class="board" style="margin-top:10px">
    <view class="board-hd"><text class="bt">驱离操作日志</text><text class="be mono">COMMAND LOG</text></view>
    <view v-for="c in (host.s?.commands || []).slice(0, 5)" :key="c.id" class="log-row mono"><text class="tm">{{ clock(c.at).slice(0, 5) }}</text><text class="msg">{{ c.message }}</text></view>
    <view v-if="!(host.s?.commands || []).length" class="empty mono">NO OPERATIONS</view>
  </view>
</template>
<style scoped>
.hd{display:flex;justify-content:space-between;align-items:center;padding:14px 16px 10px}.hd .b{font-size:18px;letter-spacing:2px;color:var(--ink-900)}.hd .s{font-size:9px;color:var(--sub);letter-spacing:2px}
.board{margin:0 14px 10px;border:1px solid var(--line)}.board-hd{display:flex;justify-content:space-between;padding:8px 10px;border-bottom:1px solid var(--line);background:var(--card)}.board-hd .bt{font-size:11px;letter-spacing:3px;color:var(--ink-900);font-weight:800}.board-hd .be{font-size:9px;color:var(--sub);letter-spacing:2px}
.cols{display:grid;grid-template-columns:64px 1fr 34px 44px 58px;padding:5px 10px;font-size:9px;letter-spacing:2px;color:var(--sub);border-bottom:1px solid var(--line)}
.row{display:grid;grid-template-columns:64px 1fr 34px 44px 58px;align-items:center;padding:0 10px;border-bottom:1px solid rgba(42,49,60,.55)}.row .fl{padding:7px 0}
.fno{font-size:11px;font-weight:700;color:var(--amber);letter-spacing:1px}
.spn{display:flex;flex-direction:column;gap:1px;min-width:0}.sn{font-size:13px;font-weight:700;color:var(--ink-900)}.ss{font-size:8.5px;color:var(--sub)}
.qty{font-size:14px;color:var(--ink-900)}.tm{font-size:11px;color:var(--dim)}.st{justify-self:end}
.flap{display:inline-block;min-width:52px;text-align:center;font-size:10px;font-weight:800;letter-spacing:2px;padding:4px 0 3px;position:relative}
.flap::after{content:'';position:absolute;left:0;right:0;top:50%;height:1px;background:rgba(0,0,0,.45)}
.flap.done{background:#171c24;color:var(--sub);border:1px solid var(--line)}
.log-row{display:flex;gap:10px;padding:6px 10px;border-bottom:1px solid rgba(42,49,60,.4);font-size:10px}.log-row .tm{color:var(--amber)}.log-row .msg{color:var(--dim)}
.empty{padding:18px;text-align:center;font-size:10px;letter-spacing:2px;color:var(--sub)}
</style>