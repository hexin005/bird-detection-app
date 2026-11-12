<script setup lang="ts">
// 信号站布局:信号站监控主页 + 其余页(B 版占位,功能完整)+ 信号站 dock
import { useHost } from '../hostContext'
import SignalMonitor from '../../theme-pages/SignalMonitor.vue'
import SignalAlarmPage from '../../theme-pages/SignalAlarmPage.vue'
import SignalControlPage from '../../theme-pages/SignalControlPage.vue'
import SignalRecordsPage from '../../theme-pages/SignalRecordsPage.vue'
import SpeciesGuide from '../pages/SpeciesGuide.vue'

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
        <view class="qh-menubar__right">
          <button class="sgn-set" aria-label="设置" @click="host.settings">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.8"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33h.01a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51h.01a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82v.01a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z" stroke="currentColor" stroke-width="1.8"/></svg>
          </button>
          <text class="time">9:41</text>
        </view>
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
    <view class="page__content"><SignalAlarmPage /></view>
  </view>

  <view class="page" :class="{ 'is-current': host.page === 'control' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__ttl">升降控制</text>
        <text class="qh-menubar__item">驱离信号</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><SignalControlPage /></view>
  </view>

  <view class="page" :class="{ 'is-current': host.page === 'records' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__ttl">记录</text>
        <text class="qh-menubar__item">观测时间轴 · 只记鸟情</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><SignalRecordsPage /></view>
  </view>

  <view class="page" :class="{ 'is-current': host.page === 'guide' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <text class="qh-menubar__back" @click="host.nav('me')">◂ 返回我的</text>
        <text class="qh-menubar__ttl">鸟类知识库</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><SpeciesGuide /></view>
  </view>

  <!-- 信号站 dock -->
  <view class="qh-tabbar">
    <view class="qh-tabbar__pill">
      <button v-for="t in tabs" :key="t.id" class="qh-tab" :class="{ 'is-active': host.page === t.id || (t.id === 'me' && ['me','themes','analytics','guide'].includes(host.page)) }" @click="host.nav(t.id)">
        <text class="sgn-tab-cn">{{ t.label }}</text>
        <text v-if="t.id === 'alarms' && host.s?.counts.pending" class="qh-tab__badge">{{ host.s.counts.pending }}</text>
      </button>
    </view>
  </view>
</template>

<style scoped>
.sgn-tab-cn { letter-spacing:2px; }
/* 信号台右上角设置:黄描边小齿轮,与 3D 沙盘按钮同族 */
.sgn-set { width:26px; height:22px; flex-shrink:0; display:flex; align-items:center; justify-content:center; background:transparent; border:1px solid #f5c400; color:#f5c400; padding:0; cursor:pointer; }
.sgn-set:active { background:rgba(245,196,0,.18); }
.sgn-set + .time { margin-left:6px; }
</style>
