<script setup lang="ts">
// 塔台布局:塔台监控主页 + 其余页(B 版占位,功能完整)+ 塔台 dock
import { useHost } from '../hostContext'
import TowerMonitor from '../../theme-pages/TowerMonitor.vue'
import TowerAlarmPage from '../../theme-pages/TowerAlarmPage.vue'
import TowerControlPage from '../../theme-pages/TowerControlPage.vue'
import TowerRecordsPage from '../../theme-pages/TowerRecordsPage.vue'

const host = useHost()
const tabs = [
  { id: 'monitor', label: '机坪' },
  { id: 'alarms', label: '告警板' },
  { id: 'control', label: '放行' },
  { id: 'records', label: '记录' },
  { id: 'me', label: '我的' },
] as const
</script>

<template>
  <!-- 机坪(监控主页,复刻) -->
  <view class="page" :class="{ 'is-current': host.page === 'monitor' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <svg width="16" height="13" viewBox="0 0 16 13" fill="none"><path d="M2 11V6L6 2h6l2 3v6h-3V8H5v3z" fill="currentColor"/><rect x="6" y="4" width="2" height="2" style="fill:var(--surface-card)"/></svg>
        <text class="qh-menubar__ttl">果园塔台</text>
        <text class="qh-menubar__item">QINGHE TWR</text>
        <view class="qh-menubar__right"><text class="time">9:41 LCL</text></view>
      </view>
    </view>
    <view class="page__content"><TowerMonitor /></view>
  </view>

  <!-- 其余页:沿用 B 版布局,功能完整可用(二期复刻) -->
  <view class="page" :class="{ 'is-current': host.page === 'alarms' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__ttl">果园塔台</text>
        <text class="qh-menubar__item">告警板 · BOARD</text>
        <view class="qh-menubar__right"><text class="time">9:41 LCL</text></view>
      </view>
    </view>
    <view class="page__content"><TowerAlarmPage /></view>
  </view>

  <view class="page" :class="{ 'is-current': host.page === 'control' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__ttl">果园塔台</text>
        <text class="qh-menubar__item">放行 · CLEARANCE</text>
        <view class="qh-menubar__right"><text class="time">9:41 LCL</text></view>
      </view>
    </view>
    <view class="page__content"><TowerControlPage /></view>
  </view>

  <view class="page" :class="{ 'is-current': host.page === 'records' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__ttl">果园塔台</text>
        <text class="qh-menubar__item">日志 · LOG</text>
        <view class="qh-menubar__right"><text class="time">9:41 LCL</text></view>
      </view>
    </view>
    <view class="page__content"><TowerRecordsPage /></view>
  </view>

  <!-- 塔台 dock -->
  <view class="qh-tabbar">
    <view class="qh-tabbar__pill">
      <button v-for="t in tabs" :key="t.id" class="qh-tab" :class="{ 'is-active': host.page === t.id || (t.id === 'me' && ['me','themes','analytics'].includes(host.page)) }" @click="host.nav(t.id)">
        <text class="twr-tab-cn">{{ t.label }}</text>
        <text v-if="t.id === 'alarms' && host.s?.counts.pending" class="qh-tab__badge">{{ host.s.counts.pending }}</text>
      </button>
    </view>
  </view>
</template>

<style scoped>
.twr-tab-cn { letter-spacing:3px; }
</style>
