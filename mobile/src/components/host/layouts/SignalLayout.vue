<script setup lang="ts">
// 信号站布局:信号站监控主页 + 其余页(B 版占位,功能完整)+ 信号站 dock
import { useHost } from '../hostContext'
import SignalMonitor from '../../theme-pages/SignalMonitor.vue'
import BAlarmsPage from '../pages/BAlarmsPage.vue'
import BControlPage from '../pages/BControlPage.vue'
import BRecordsPage from '../pages/BRecordsPage.vue'

const host = useHost()
const tabs = [
  { id: 'monitor', label: '信号台' },
  { id: 'alarms', label: '告警' },
  { id: 'control', label: '升降' },
  { id: 'records', label: '记录' },
  { id: 'me', label: '我的' },
] as const
</script>

<template>
  <!-- 信号台(监控主页,复刻) -->
  <view class="page" :class="{ 'is-current': host.page === 'monitor' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__back" @click="host.nav('monitor')" style="display:none"/>
        <svg width="16" height="13" viewBox="0 0 16 13" fill="none"><path d="M2 11V6L6 2h6l2 3v6h-3V8H5v3z" fill="currentColor"/><rect x="6" y="4" width="2" height="2" style="fill:var(--surface-card)"/></svg>
        <text class="qh-menubar__ttl">信号台</text>
        <text class="qh-menubar__item">ST.01 东区</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><SignalMonitor /></view>
  </view>

  <!-- 其余页:B 版布局占位(二期复刻),功能完整可用 -->
  <view class="page" :class="{ 'is-current': host.page === 'alarms' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__ttl">告警</text>
        <text class="qh-menubar__item">待人工确认后执行驱离</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><BAlarmsPage /></view>
  </view>

  <view class="page" :class="{ 'is-current': host.page === 'control' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__ttl">升降控制</text>
        <text class="qh-menubar__item">驱离信号</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><BControlPage /></view>
  </view>

  <view class="page" :class="{ 'is-current': host.page === 'records' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__ttl">记录</text>
        <text class="qh-menubar__item">按视频回看</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><BRecordsPage /></view>
  </view>

  <!-- 信号站 dock -->
  <view class="qh-tabbar">
    <view class="qh-tabbar__pill">
      <button v-for="t in tabs" :key="t.id" class="qh-tab" :class="{ 'is-active': host.page === t.id || (t.id === 'me' && ['me','themes','analytics'].includes(host.page)) }" @click="host.nav(t.id)">
        <text class="sgn-tab-cn">{{ t.label }}</text>
        <text v-if="t.id === 'alarms' && host.s?.counts.pending" class="qh-tab__badge">{{ host.s.counts.pending }}</text>
      </button>
    </view>
  </view>
</template>

<style scoped>
.sgn-tab-cn { letter-spacing:2px; }
</style>
