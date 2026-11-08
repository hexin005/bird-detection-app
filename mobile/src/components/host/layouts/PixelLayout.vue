<script setup lang="ts">
// 像素布局:像素监控主页 + 其余页(B 版占位,功能完整)+ 像素 dock
import { useHost } from '../hostContext'
import PixelMonitor from '../../theme-pages/PixelMonitor.vue'
import BAlarmsPage from '../pages/BAlarmsPage.vue'
import BControlPage from '../pages/BControlPage.vue'
import BRecordsPage from '../pages/BRecordsPage.vue'

const host = useHost()
const tabs = [
  { id: 'monitor', label: '机坪' },
  { id: 'alarms', label: '告警' },
  { id: 'control', label: '放行' },
  { id: 'records', label: '图鉴' },
  { id: 'me', label: '我的' },
] as const
</script>

<template>
  <!-- 机坪(监控主页,复刻) -->
  <view class="page" :class="{ 'is-current': host.page === 'monitor' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <svg width="16" height="13" viewBox="0 0 16 13" fill="none"><path d="M2 11V6L6 2h6l2 3v6h-3V8H5v3z" fill="currentColor"/><rect x="6" y="4" width="2" height="2" style="fill:var(--surface-card)"/></svg>
        <text class="qh-menubar__ttl">像素果园</text>
        <text class="qh-menubar__item">PIXEL ORCHARD</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><PixelMonitor /></view>
  </view>

  <!-- 其余页:B 版布局占位(二期复刻),功能完整可用 -->
  <view class="page" :class="{ 'is-current': host.page === 'alarms' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__ttl">告警</text>
        <text class="qh-menubar__item">! 出现的野生鸟类</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><BAlarmsPage /></view>
  </view>

  <view class="page" :class="{ 'is-current': host.page === 'control' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__ttl">放行</text>
        <text class="qh-menubar__item">驱离道具</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><BControlPage /></view>
  </view>

  <view class="page" :class="{ 'is-current': host.page === 'records' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__ttl">图鉴</text>
        <text class="qh-menubar__item">观测档案</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><BRecordsPage /></view>
  </view>

  <!-- 像素 dock -->
  <view class="qh-tabbar">
    <view class="qh-tabbar__pill">
      <button v-for="t in tabs" :key="t.id" class="qh-tab" :class="{ 'is-active': host.page === t.id || (t.id === 'me' && ['me','themes','analytics'].includes(host.page)) }" @click="host.nav(t.id)">
        <text class="px-tab-cn">{{ t.label }}</text>
        <text v-if="t.id === 'alarms' && host.s?.counts.pending" class="qh-tab__badge">{{ host.s.counts.pending }}</text>
      </button>
    </view>
  </view>
</template>

<style scoped>
.px-tab-cn { letter-spacing:2px; }
</style>
