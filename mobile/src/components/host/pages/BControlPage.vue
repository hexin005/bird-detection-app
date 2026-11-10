<script setup lang="ts">
// B 主题控制页(S1 自动哨兵):头部 + 快速驱离条 + 共享策略层(规则/巡逻/参数) + 最近执行。
// 策略卡结构与文案在 ControlStrategy 共享,四主题一致,观感走 token。
import { computed } from 'vue'
import { useHost, modeCn, type RepelMode } from '../hostContext'
import ControlStrategy from '../ControlStrategy.vue'

const host = useHost()

/* ---- 快速驱离(单次,语义与首页一致) ---- */
function openConfirm() { host.modal = 'mConfirm' }

const recentTotal = computed(() => host.s?.counts.completed || 0)
</script>

<template>
  <view class="qh-header__brand">
    <view class="sn-titlerow">
      <text class="qh-page-title">自动哨兵</text>
      <text class="qh-badge qh-badge--new">策略层</text>
    </view>
    <text class="qh-page-subtitle">首页管「现在这一下」· 这里管「以后每一刻」</text>
  </view>

  <!-- 快速驱离:单次动作紧凑条 -->
  <view class="sn-card">
    <view class="sn-card__hd"><text class="t">快速驱离</text><text class="s">手动单次 · 与首页相同能力</text></view>
    <view class="sn-quick">
      <view class="sn-chips">
        <text v-for="m in ['acoustic', 'infrared', 'both']" :key="m" class="sn-chip" :class="{ 'is-on': host.mode === m }" @click="host.mode = m as RepelMode">{{ modeCn[m as RepelMode] }}</text>
        <text v-for="d in [3, 5, 8]" :key="d" class="sn-chip" :class="{ 'is-on': host.duration === d }" @click="host.duration = d">{{ d }}秒</text>
      </view>
      <button class="sn-go" :disabled="host.store.busy || host.offline || !!host.store.active" @click="openConfirm">▶ 执行</button>
    </view>
    <view v-if="host.store.active" class="sn-active mono">{{ host.remaining }}s · {{ host.store.active.message }}</view>
  </view>

  <!-- 策略层:规则 / 巡逻 / 参数(共享组件) -->
  <ControlStrategy />

  <!-- 最近执行 -->
  <view class="sn-card sn-strip" @click="host.recordMode = 'actions'; host.nav('records')">
    <text class="t">最近执行 {{ recentTotal }} 次 · 点看执行日志</text><text class="arrow">›</text>
  </view>

  <text class="qh-note">本设备是模拟执行器，不会控制真实硬件 · 自动指令同样遵守离线/互斥边界</text>
</template>

<style scoped>
.sn-titlerow{display:flex;align-items:center;gap:10px}
.sn-card{margin:0 14px 12px;border:2px solid var(--ink-900);background:var(--surface-card);box-shadow:4px 4px 0 var(--shadow-ink);padding:11px 13px}
.sn-card__hd{display:flex;align-items:center;gap:9px;margin-bottom:9px}
.sn-card__hd .t{flex:1;font-size:13.5px;font-weight:800;color:var(--ink-900);letter-spacing:1px}
.sn-card__hd .s{font-size:10px;color:var(--ink-400)}
.sn-quick{display:flex;align-items:center;gap:9px}
.sn-chips{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.sn-chip{border:2px solid var(--ink-900);background:var(--surface-card);color:var(--ink-900);font-size:11px;font-weight:700;padding:4px 10px;white-space:nowrap;cursor:pointer}
.sn-chip.is-on{background:var(--ink-900);color:var(--surface-card)}
.sn-go{border:2px solid var(--ink-900);background:var(--ink-900);color:var(--surface-card);font-size:13px;font-weight:800;padding:9px 16px;box-shadow:3px 3px 0 var(--shadow-ink);cursor:pointer;flex-shrink:0;border-radius:0}
.sn-go[disabled]{opacity:.45;box-shadow:none}
.sn-active{margin-top:9px;font-size:11px;color:var(--ink-400)}
.sn-strip{display:flex;align-items:center;justify-content:space-between;cursor:pointer}
.sn-strip .t{font-size:12px;font-weight:700;color:var(--ink-900)}
.sn-strip .arrow{color:var(--ink-400);font-size:15px}
</style>
