<script setup lang="ts">
import { useHost, names, clock, shortTime, time, alarmClass } from '../host/hostContext'
import type { RepelMode } from '../host/hostContext'

const host = useHost()
</script>
<template>
  <view style="padding:12px"><b style="font-size:16px;color:#10130c">▶ 放行 · 驱离道具</b></view>
  <view class="card">
    <b class="t">选择驱离道具</b>
    <view class="opts">
      <span v-for="m in [{ id: 'acoustic', n: '声波喇叭' }, { id: 'infrared', n: '红外脉冲' }, { id: 'both', n: '双模联动' }]" :key="m.id" :class="{ on: host.mode === m.id }" style="cursor:pointer" @click="host.mode = (m.id as RepelMode)">{{ m.n }}</span>
    </view>
    <b style="font-size:10px;color:#f8d94a;font-weight:800;letter-spacing:2px;display:block;margin-top:10px">使用时长</b>
    <view class="opts"><span v-for="d in [3,5,8]" :key="d" :class="{ on: host.duration === d }" style="cursor:pointer" @click="host.duration = d">{{ d }}s</span></view>
    <button class="use" :disabled="host.store.busy || host.offline || !!host.store.active || !host.pending.length" @click="host.modal = 'mConfirm'">▶ 使用道具 · {{ host.mode === 'acoustic' ? '声波驱离' : host.mode === 'infrared' ? '红外驱离' : '双模驱离' }}</button>
    <p class="hint">使用后鸟群会散去一部分 · 需多次使用才能全部清空</p>
  </view>
  <view class="card">
    <b class="t">使用记录</b>
    <p v-for="c in (host.s?.commands || []).slice(0, 4)" :key="c.id" :style="{ color: c.status === 'completed' ? '#8fe08f' : '#7f8a72' }">▸ {{ shortTime(c.at) }} {{ host.mode === 'acoustic' ? '声波' : host.mode === 'infrared' ? '红外' : '双模' }} · {{ names(c.status) }}</p>
    <p v-if="!(host.s?.commands || []).length" style="color:#7f8a72">暂无使用记录</p>
  </view>
</template>
<style scoped>
.card{background:#10130c;border:4px solid #f4f1e4;box-shadow:0 0 0 4px #10130c,0 6px 0 rgba(0,0,0,.45);padding:12px 13px;margin:12px;position:relative}
.t{color:#f8d94a;font-size:10px;font-weight:800;letter-spacing:2px;display:block;margin-bottom:8px}
.opts{display:flex;gap:6px;margin-top:6px}
.opts span{flex:1;border:2px solid #f4f1e4;color:#f4f1e4;font-size:11px;font-weight:800;text-align:center;padding:6px 0;cursor:pointer}
.opts .on{background:#f4f1e4;color:#10130c}
.use{display:block;width:100%;background:#8fe08f;color:#10130c;font-size:13px;font-weight:800;text-align:center;padding:10px 0;margin-top:12px;border:3px solid #10130c;box-shadow:0 3px 0 #10130c;cursor:pointer}
.use[disabled]{background:#3a4130;color:#7f8a72;border-color:#3a4130;box-shadow:none}
.hint{font-size:10px;color:#7f8a72;margin-top:8px}
p{font-size:11px;font-weight:700;line-height:1.6;margin-top:4px}
</style>