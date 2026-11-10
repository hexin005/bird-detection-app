<script setup lang="ts">
import { useHost, names, clock, shortTime, time, alarmClass } from '../host/hostContext'
import type { RepelMode } from '../host/hostContext'
import ControlStrategy from '../host/ControlStrategy.vue'

const host = useHost()
</script>
<template>
  <view class="hd"><text class="b">升降控制</text><text class="s">手动单次 · 自动策略见下方</text></view>
  <view class="ctl">
    <view class="hz"/>
    <view class="bd">
      <view class="row"><text class="t">驱离方式</text><text class="note">红外与声学可双模联动</text></view>
      <view class="flags">
        <view v-for="m in [{ id: 'acoustic', n: '▲ 声波', en: 'ACOUSTIC 01' }, { id: 'infrared', n: '▲ 红外', en: 'INFRARED 02' }, { id: 'both', n: '▲▲ 双模联挂', en: 'DUAL-MODE' }]" :key="m.id" class="flag" :class="{ on: host.mode === m.id }" @click="host.mode = (m.id as RepelMode)">
          <text class="n">{{ m.n }}</text><text class="en mono">{{ m.en }}</text>
        </view>
      </view>
      <view class="row"><text class="t">单次执行时长</text><text class="note">定时结束 · 不连续运行</text></view>
      <view class="durs"><text v-for="d in [3,5,8]" :key="d" class="dur" :class="{ on: host.duration === d }" @click="host.duration = d">{{ d }} 秒</text></view>
      <button class="raise" :disabled="host.store.busy || host.offline || !!host.store.active" @click="host.modal = 'mConfirm'">
        <text class="raise-t">升起驱离信号</text>
        <text class="raise-s mono">{{ host.offline ? '设备离线 · 无法升起' : host.store.active ? '信号升空中 · ' + Math.max(0, host.remaining) + 's' : '关联 ' + (host.selectedAlarm || '手动操作') + ' · 人工确认后执行' }}</text>
      </button>
    </view>
  </view>

  <!-- 策略层:自动响应规则 / 定时巡逻 / 设备参数(共享组件) -->
  <ControlStrategy />
</template>
<style scoped>
.hd{display:flex;justify-content:space-between;align-items:center;padding:14px 16px 10px}.hd .b{font-size:16px;font-weight:900;letter-spacing:2px;color:var(--ink-900)}.hd .s{font-size:9px;color:var(--ink-400)}
.ctl{margin:0 16px;border:2px solid #191919;background:#fbfaf4}
.hz{height:10px;background:repeating-linear-gradient(-45deg,#f5c400 0 12px,#191919 12px 24px);border-bottom:2px solid #191919}
.bd{padding:12px}
.row{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}.row .t{font-size:13px;font-weight:900;letter-spacing:2px}.row .note{font-size:9px;color:var(--ink-400)}
.flags{display:flex;gap:8px;margin-bottom:9px}
.flag{flex:1;border:2px solid #191919;padding:7px 0 6px;text-align:center;font-size:11.5px;font-weight:800;display:flex;flex-direction:column;gap:1px;color:#191919;cursor:pointer}
.flag .en{font-size:8px;letter-spacing:1px;color:var(--ink-400);font-weight:700}
.flag.on{background:#191919;color:#f2f1ea}
.flag.on .en{color:#9a9a92}
.durs{display:flex;gap:6px;margin-bottom:9px}
.dur{flex:1;border:2px solid #191919;text-align:center;font-size:11px;font-weight:800;padding:6px 0;color:#191919;cursor:pointer}
.dur.on{background:#191919;color:#f5c400}
.raise{background:#191919;color:#f5c400;font-size:14px;font-weight:900;letter-spacing:4px;text-align:center;padding:12px 0;border:none;display:flex;flex-direction:column;gap:2px;width:100%;cursor:pointer}
.raise[disabled]{background:#6f6f68;color:#d9d8d0}
.raise .raise-s{font-size:9px;letter-spacing:2px;color:#9a9a92;font-weight:700}
</style>