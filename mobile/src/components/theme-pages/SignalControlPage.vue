<script setup lang="ts">
// C 升降「远程控制台」:设备挂牌牌桌(状态灯) + 驱离方式旗 + 时长拨盘 + 警示纹主杆;
// 语义动作与共享 ControlStrategy 不变,状态灯绑定真实场景离线态。
import { useHost } from '../host/hostContext'
import type { RepelMode } from '../host/hostContext'
import ControlStrategy from '../host/ControlStrategy.vue'

const host = useHost()
const modes = [
  { id: 'acoustic', n: '▲ 声波', en: 'ACOUSTIC 01' },
  { id: 'infrared', n: '▲ 红外', en: 'INFRARED 02' },
  { id: 'both', n: '▲▲ 双模联挂', en: 'DUAL-MODE' },
] as const
const durs = [
  { v: 3, label: '快速' },
  { v: 5, label: '标准' },
  { v: 8, label: '加强' },
] as const
</script>

<template>
  <view class="rc-head">
    <view><text class="eyebrow">REMOTE CONSOLE</text><text class="title">升降控制台</text></view>
    <text class="hztag">REMOTE</text>
  </view>

  <!-- 设备牌桌:状态灯跟随场景离线态 -->
  <view class="rc-plates">
    <view class="plate"><text class="nm">声学驱鸟器 01</text><text class="en mono">ACOUSTIC 01 · 东区</text><text class="lamp" :class="{ off: host.offline }"><i/>{{ host.offline ? '离线' : '在线' }}</text><text class="bars">▲▲▲</text></view>
    <view class="plate"><text class="nm">红外驱鸟器 02</text><text class="en mono">INFRARED 02 · 东区</text><text class="lamp" :class="{ off: host.offline }"><i/>{{ host.offline ? '离线' : '在线' }}</text><text class="bars">▲▲▲</text></view>
  </view>

  <view class="rc-sec"><text class="b">驱离方式</text><text class="s">红外与声学可双模联动</text></view>
  <view class="rc-flags">
    <view v-for="m in modes" :key="m.id" class="flag" :class="{ on: host.mode === m.id }" @click="host.mode = (m.id as RepelMode)">
      <text class="n">{{ m.n }}</text><text class="en mono">{{ m.en }}</text>
    </view>
  </view>

  <view class="rc-sec"><text class="b">单次时长</text><text class="s">定时结束自动降下</text></view>
  <view class="rc-durs">
    <view v-for="d in durs" :key="d.v" class="dur" :class="{ on: host.duration === d.v }" @click="host.duration = d.v">
      <text class="v mono">{{ d.v }}</text><text class="l">秒 · {{ d.label }}</text>
    </view>
  </view>

  <view class="rc-raise" :class="{ disabled: host.store.busy || host.offline || !!host.store.active }" @click="!(host.store.busy || host.offline || !!host.store.active) && (host.modal = 'mConfirm')">
    <i class="rivet l"/><i class="rivet r"/>
    <view class="hz"/>
    <text class="t">升起驱离信号</text>
    <text class="s mono">{{ host.offline ? '设备离线 · 无法升起' : host.store.active ? '信号升空中 · ' + Math.max(0, host.remaining) + 's' : '关联 ' + (host.selectedAlarm || '手动操作') + ' · 人工确认后执行' }}</text>
  </view>

  <view class="rc-sec"><text class="b">自动策略</text><text class="s">触发条件满足时自动升牌</text></view>
  <ControlStrategy />
</template>

<style scoped>
/* ===== 头部 ===== */
.rc-head{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:14px 16px 10px}
.rc-head>view{display:flex;flex-direction:column;gap:3px}
.eyebrow{font-size:8.5px;letter-spacing:2px;color:var(--ink-400);font-weight:700}
.title{font-size:19px;font-weight:900;letter-spacing:3px;color:var(--ink-900)}
.hztag{border:2px solid var(--ink-900);font-size:9px;font-weight:900;letter-spacing:1px;padding:3px 6px;background:repeating-linear-gradient(-45deg,#f5c400 0 8px,var(--ink-900) 8px 16px);color:var(--ink-900);text-shadow:0 0 3px var(--surface-canvas)}
/* 设备牌桌 */
.rc-plates{display:flex;gap:10px;margin:0 14px}
.plate{flex:1;background:var(--surface-card);border:2px solid var(--ink-900);box-shadow:3px 4px 0 var(--shadow-ink);position:relative;padding:15px 8px 10px;text-align:center}
.plate::before{content:'';position:absolute;left:50%;top:4px;transform:translateX(-50%);width:9px;height:9px;border-radius:50%;background:var(--surface-canvas);border:2px solid var(--ink-900)}
.plate .nm{display:block;font-size:12.5px;font-weight:900;letter-spacing:1px;color:var(--ink-900)}
.plate .en{display:block;font-size:8px;color:var(--ink-400);letter-spacing:2px;margin-top:2px}
.plate .lamp{display:inline-flex;align-items:center;gap:5px;margin-top:7px;border:2px solid var(--ink-900);padding:2px 8px;font-size:9px;font-weight:900;color:var(--ink-900)}
.plate .lamp i{width:8px;height:8px;border-radius:50%;background:#f5c400;border:1px solid var(--ink-900)}
.plate .lamp.off i{background:#d3212c}
.plate .bars{display:block;margin-top:6px;font-size:9px;letter-spacing:2px;color:var(--ink-900)}
/* 分节标题 */
.rc-sec{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:15px 14px 8px}
.rc-sec .b{font-size:12.5px;font-weight:900;letter-spacing:2px;color:var(--ink-900)}
.rc-sec .s{font-size:9px;color:var(--ink-400)}
/* 方式旗 */
.rc-flags{display:flex;gap:8px;margin:0 14px}
.flag{flex:1;border:2px solid var(--ink-900);background:var(--surface-card);padding:9px 0 8px;text-align:center;box-shadow:3px 3px 0 var(--shadow-ink);cursor:pointer}
.flag .n{display:block;font-size:12px;font-weight:900;color:var(--ink-900)}
.flag .en{display:block;font-size:8px;color:var(--ink-400);letter-spacing:1px;margin-top:2px}
.flag.on{background:var(--ink-900);transform:translate(-1px,-1px);box-shadow:4px 4px 0 var(--shadow-ink)}
.flag.on .n{color:#f5c400}
.flag.on .en{color:#9a9a92}
/* 时长拨盘 */
.rc-durs{display:flex;gap:8px;margin:0 14px}
.dur{flex:1;border:2px solid var(--ink-900);background:var(--surface-card);text-align:center;padding:9px 0;box-shadow:3px 3px 0 var(--shadow-ink);cursor:pointer}
.dur .v{display:block;font-size:17px;font-weight:700;color:var(--ink-900)}
.dur .l{display:block;font-size:8px;color:var(--ink-400);letter-spacing:2px;margin-top:1px}
.dur.on{background:#f5c400}
.dur.on .l{color:var(--ink-900)}
/* 升起主杆 */
.rc-raise{margin:14px 14px 0;border:2px solid var(--ink-900);background:var(--ink-900);position:relative;cursor:pointer;box-shadow:4px 5px 0 var(--shadow-ink)}
.rc-raise.disabled{cursor:default;opacity:.55;box-shadow:none}
.rc-raise .hz{height:8px;background:repeating-linear-gradient(-45deg,#f5c400 0 10px,var(--ink-900) 10px 20px);border-bottom:2px solid #f5c400}
.rc-raise .t{display:block;color:#f5c400;font-size:15px;font-weight:900;letter-spacing:5px;text-align:center;padding:12px 0 2px}
.rc-raise .s{display:block;text-align:center;font-size:9px;color:#9a9a92;letter-spacing:1px;padding-bottom:11px}
.rc-raise .rivet{position:absolute;width:7px;height:7px;border-radius:50%;background:#f5c400;top:15px}
.rc-raise .rivet.l{left:9px}
.rc-raise .rivet.r{right:9px}
</style>
