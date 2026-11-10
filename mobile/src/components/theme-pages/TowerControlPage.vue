<script setup lang="ts">
import { useHost, names, clock, shortTime, time, badgeText, monClass, alarmClass, type RepelMode } from '../host/hostContext'
import { useWorkspace } from '../host/useWorkspace'
import { useOrchard } from '../../store'
import ControlStrategy from '../host/ControlStrategy.vue'

const host = useHost()
const store = useOrchard()
const ws = useWorkspace(store)
</script>
<template>
  <view class="hd"><text class="b">放行许可</text><text class="s mono">CLEARANCE</text></view>
  <view class="cl">
    <view class="cl-hd mono"><text class="t">CLEARANCE · 放行许可</text><text class="l">{{ host.selectedAlarm ? '关联 ' + host.selectedAlarm.slice(0, 8) : '手动操作' }}</text></view>
    <view class="cl-body">
      <view class="cl-modes">
        <view v-for="m in [{ id: 'acoustic', n: '声波', en: 'ACOUSTIC' }, { id: 'infrared', n: '红外', en: 'INFRARED' }, { id: 'both', n: '双模联动', en: 'DUAL-MODE' }]" :key="m.id" class="cl-mode" :class="{ on: host.mode === m.id }" @click="host.mode = (m.id as RepelMode)">
          <text class="n">{{ m.n }}</text><text class="en mono">{{ m.en }}</text>
        </view>
      </view>
      <button class="cl-go" :disabled="host.store.busy || host.offline || !!host.store.active" @click="host.modal = 'mConfirm'">
        <text class="go-t">确认放行</text><text class="go-s mono">{{ host.offline ? '设备离线' : host.store.active ? '执行中' : `双模 · ${host.duration} 秒` }}</text>
      </button>
    </view>
  </view>
  <view class="cl dur">
    <text class="cl-hd-t">单次执行时长</text>
    <view class="cl-durs"><text v-for="d in [3,5,8]" :key="d" class="cl-dur" :class="{ on: host.duration === d }" @click="host.duration = d">{{ d }} 秒</text></view>
  </view>
  <view v-if="host.store.active" class="cl prog">
    <text class="cl-hd-t">驱离执行中</text>
    <view class="cl-prog-bar"><view :style="{ width: Math.min(100, (1 - host.remaining / host.store.active!.duration) * 100) + '%' }"/></view>
    <text class="cl-prog-s mono">{{ host.remaining }}s · {{ host.store.active.message }}</text>
    <button class="cl-stop" @click="host.run(() => host.store.mutate('/commands/' + host.store.active!.id + '/stop'))">停止本次执行</button>
  </view>
  <text class="note">模拟执行器 · 不会控制真实硬件</text>

  <!-- 策略层:自动响应规则 / 定时巡逻 / 设备参数(共享组件) -->
  <ControlStrategy />
</template>
<style scoped>
.hd{display:flex;justify-content:space-between;align-items:center;padding:14px 16px 10px}.hd .b{font-size:18px;letter-spacing:2px;color:var(--ink-900)}.hd .s{font-size:9px;color:var(--ink-400);letter-spacing:2px}
.cl{margin:0 14px 10px;border:1px solid #8a6a1e;background:var(--surface-card)}
.cl-hd{display:flex;justify-content:space-between;padding:6px 10px;border-bottom:1px dashed var(--line);font-size:9px;letter-spacing:2px}.cl-hd .t{color:var(--accent);font-weight:700}.cl-hd .l{color:var(--ink-400)}
.cl-body{display:flex;align-items:stretch}.cl-modes{display:flex;flex:1}
.cl-mode{flex:1;text-align:center;padding:9px 0 8px;font-size:11px;font-weight:700;letter-spacing:2px;color:var(--ink-400);border-right:1px solid var(--line);display:flex;flex-direction:column;gap:2px;cursor:pointer}
.cl-mode .en{font-size:8px;letter-spacing:1px;color:#3d4756;font-weight:400}
.cl-mode.on{color:#161307;background:var(--accent)}.cl-mode.on .en{color:rgba(22,19,7,.65)}
.cl-go{width:96px;text-align:center;background:var(--accent);color:#161307;font-weight:800;font-size:12px;letter-spacing:2px;border:none;display:flex;flex-direction:column;justify-content:center;gap:2px;cursor:pointer}
.cl-go[disabled]{background:#20262f;color:#5d6672}
.cl-go .go-s{font-size:9px;letter-spacing:1px;opacity:.7}
.dur{padding:10px}.cl-hd-t{font-size:11px;letter-spacing:2px;color:var(--ink-900);font-weight:800}
.cl-durs{display:flex;gap:6px;margin-top:8px}.cl-dur{flex:1;text-align:center;padding:6px 0;font-size:11px;font-weight:700;border:1px solid var(--line);color:var(--ink-700);cursor:pointer}
.cl-dur.on{border-color:var(--accent);color:var(--accent)}
.prog{padding:10px}.cl-prog-bar{height:6px;background:#12161c;border:1px solid var(--line);margin-top:6px}.cl-prog-bar view{height:100%;background:var(--accent)}
.cl-prog-s{font-size:10px;color:var(--ink-500);margin-top:4px}.cl-stop{width:100%;margin-top:8px;background:transparent;border:1px solid var(--line);color:var(--ink-500);font-size:11px;padding:6px 0;cursor:pointer}
.note{text-align:center;font-size:10px;color:var(--ink-400);padding:6px}
</style>