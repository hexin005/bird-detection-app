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
  <!-- 最新一报:直接处置(A1 语义) -->
  <view v-if="host.pending.length" class="latest">
    <view class="latest-hd mono"><text>LATEST · BRD-{{ host.pending[0].id.slice(-4).toUpperCase() }}</text><text>{{ clock(host.pending[0].at).slice(0, 5) }}</text></view>
    <view class="latest-bd">
      <text class="sp">{{ host.pending[0].species }} ×{{ host.pending[0].count }}</text>
      <view class="la-row">
        <button class="la main" :disabled="host.store.busy || host.offline || !!host.store.active" @click="host.quickRepel(host.pending[0].id)">▶ 放行驱离</button>
        <button class="la" :disabled="host.store.busy" @click="host.run(() => host.requestIgnore(host.pending[0].id))">忽略</button>
      </view>
    </view>
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
.hd{display:flex;justify-content:space-between;align-items:center;padding:14px 16px 10px}.hd .b{font-size:18px;letter-spacing:2px;color:var(--ink-900)}.hd .s{font-size:9px;color:var(--ink-400);letter-spacing:2px}
.board{margin:0 14px 10px;border:1px solid var(--line)}.board-hd{display:flex;justify-content:space-between;padding:8px 10px;border-bottom:1px solid var(--line);background:var(--surface-card)}.board-hd .bt{font-size:11px;letter-spacing:3px;color:var(--ink-900);font-weight:800}.board-hd .be{font-size:9px;color:var(--ink-400);letter-spacing:2px}
.cols{display:grid;grid-template-columns:64px 1fr 34px 44px 58px;padding:5px 10px;font-size:9px;letter-spacing:2px;color:var(--ink-400);border-bottom:1px solid var(--line)}
.row{display:grid;grid-template-columns:64px 1fr 34px 44px 58px;align-items:center;padding:0 10px;border-bottom:1px solid rgba(42,49,60,.55)}.row .fl{padding:7px 0}
.fno{font-size:11px;font-weight:700;color:var(--accent);letter-spacing:1px}
.spn{display:flex;flex-direction:column;gap:1px;min-width:0}.sn{font-size:13px;font-weight:700;color:var(--ink-900);letter-spacing:1px}.ss{font-size:8.5px;color:var(--ink-400);letter-spacing:1.5px}
.qty{font-size:14px;color:var(--ink-900)}.tm{font-size:11px;color:var(--ink-500)}.st{justify-self:end}
.flap{display:inline-block;min-width:52px;text-align:center;font-size:10px;font-weight:800;letter-spacing:2px;padding:4px 0 3px;position:relative}
.flap::after{content:'';position:absolute;left:0;right:0;top:50%;height:1px;background:rgba(0,0,0,.45)}
.flap.new{background:var(--warn-bg);color:var(--warn-fg)}.flap.done,.flap.ign{background:#171c24;color:var(--ink-400);border:1px solid var(--line)}
.flap.processing,.flap.running{background:var(--accent);color:#161307;animation:qhBlink 1.4s steps(2) infinite}
.row.is-new{background:linear-gradient(90deg,rgba(255,75,62,.12),transparent 65%);box-shadow:inset 3px 0 0 var(--warn-bg)}
.empty{padding:20px;text-align:center;font-size:10px;letter-spacing:2px;color:var(--ink-400)}

.latest{margin:0 14px 10px;border:1px solid var(--warn-line);background:var(--surface-card)}
.latest-hd{display:flex;justify-content:space-between;padding:6px 10px;font-size:9px;letter-spacing:2px;color:var(--ink-400);border-bottom:1px dashed var(--line)}
.latest-bd{display:flex;align-items:center;gap:10px;padding:9px 10px}
.latest-bd .sp{flex:1;font-size:14px;font-weight:800;color:var(--ink-900);letter-spacing:1px}
.la-row{display:flex;gap:6px}
.la{border:1px solid var(--line);background:transparent;color:var(--ink-400);font-size:11px;font-weight:700;letter-spacing:2px;padding:7px 12px;cursor:pointer}
.la.main{background:var(--warn-bg);color:var(--warn-fg);border-color:var(--warn-bg)}
.la[disabled]{opacity:.45}
</style>