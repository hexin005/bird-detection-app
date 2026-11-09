<script setup lang="ts">
import { useHost, names, clock, shortTime, time, badgeText, monClass, alarmClass, type RepelMode } from '../host/hostContext'
import { useWorkspace } from '../host/useWorkspace'
import { useOrchard } from '../../store'

const host = useHost()
const store = useOrchard()
const ws = useWorkspace(store)
</script>
<template>
  <view class="hd"><text class="b">告警板 BOARD</text><text class="s mono">ALARMS · {{ host.s?.counts.pending || 0 }} PENDING</text></view>
  <view class="board">
    <view class="board-hd"><text class="bt">待处理告警</text><text class="be mono">NEW ALARMS</text></view>
    <view class="cols mono"><text>班次</text><text>鸟种</text><text>数量</text><text>时刻</text><text style="text-align:right">状态</text></view>
    <view v-for="a in host.s?.alarms.filter(a => a.status === 'new').slice(0, 6)" :key="a.id" class="row is-new" style="cursor:pointer" @click="host.openAlarm(a)">
      <text class="fno mono">BRD-{{ a.id.slice(-4).toUpperCase() }}</text>
      <view class="spn"><text class="sn">{{ a.species }} ×{{ a.count }}</text><text class="ss mono">置信度 {{ Math.round(a.confidence * 100) }}%</text></view>
      <text class="qty mono">{{ a.count }}</text><text class="tm mono">{{ clock(a.at).slice(0, 5) }}</text>
      <view class="st"><text class="flap new mono">待处理</text></view>
    </view>
    <view v-if="!host.pending.length" class="empty mono">NO NEW ALARMS · 果园平静</view>
  </view>
  <view class="board" style="margin-top:10px">
    <view class="board-hd"><text class="bt">已处理日志</text><text class="be mono">RESOLVED</text></view>
    <view class="cols mono"><text>班次</text><text>鸟种</text><text>数量</text><text>时刻</text><text style="text-align:right">状态</text></view>
    <view v-for="a in (host.s?.alarms || []).filter(a => a.status !== 'new').slice(0, 5)" :key="a.id" class="row" style="cursor:pointer" @click="host.openAlarm(a)">
      <text class="fno mono">BRD-{{ a.id.slice(-4).toUpperCase() }}</text>
      <view class="spn"><text class="sn">{{ a.species }} ×{{ a.count }}</text><text class="ss mono">置信度 {{ Math.round(a.confidence * 100) }}%</text></view>
      <text class="qty mono">{{ a.count }}</text><text class="tm mono">{{ clock(a.at).slice(0, 5) }}</text>
      <view class="st"><text class="flap done mono">{{ names(a.status) }}</text></view>
    </view>
  </view>
</template>
<style scoped>
.hd{display:flex;justify-content:space-between;align-items:center;padding:14px 16px 10px}.hd .b{font-size:18px;letter-spacing:2px;color:var(--ink-900)}.hd .s{font-size:9px;color:var(--sub);letter-spacing:2px}
.board{margin:0 14px 10px;border:1px solid var(--line)}.board-hd{display:flex;justify-content:space-between;padding:8px 10px;border-bottom:1px solid var(--line);background:var(--card)}.board-hd .bt{font-size:11px;letter-spacing:3px;color:var(--ink-900);font-weight:800}.board-hd .be{font-size:9px;color:var(--sub);letter-spacing:2px}
.cols{display:grid;grid-template-columns:64px 1fr 34px 44px 58px;padding:5px 10px;font-size:9px;letter-spacing:2px;color:var(--sub);border-bottom:1px solid var(--line)}
.row{display:grid;grid-template-columns:64px 1fr 34px 44px 58px;align-items:center;padding:0 10px;border-bottom:1px solid rgba(42,49,60,.55)}.row .fl{padding:7px 0}
.fno{font-size:11px;font-weight:700;color:var(--accent);letter-spacing:1px}
.spn{display:flex;flex-direction:column;gap:1px;min-width:0}.sn{font-size:13px;font-weight:700;color:var(--ink-900);letter-spacing:1px}.ss{font-size:8.5px;color:var(--sub);letter-spacing:1.5px}
.qty{font-size:14px;color:var(--ink-900)}.tm{font-size:11px;color:var(--dim)}.st{justify-self:end}
.flap{display:inline-block;min-width:52px;text-align:center;font-size:10px;font-weight:800;letter-spacing:2px;padding:4px 0 3px;position:relative}
.flap::after{content:'';position:absolute;left:0;right:0;top:50%;height:1px;background:rgba(0,0,0,.45)}
.flap.new{background:var(--red);color:#160b0a}.flap.done,.flap.ign{background:#171c24;color:var(--sub);border:1px solid var(--line)}
.flap.processing,.flap.running{background:var(--amber);color:#161307;animation:qhBlink 1.4s steps(2) infinite}
.row.is-new{background:linear-gradient(90deg,rgba(255,75,62,.12),transparent 65%);box-shadow:inset 3px 0 0 var(--red)}
.empty{padding:20px;text-align:center;font-size:10px;letter-spacing:2px;color:var(--sub)}
</style>