<script setup lang="ts">
// B 主题布局:四页编排 + dock(五个语义入口)。页面内容来自 Host 公共组件。
import { useHost } from '../hostContext'
import BMonitorPage from '../pages/BMonitorPage.vue'
import BAlarmsPage from '../pages/BAlarmsPage.vue'
import BControlPage from '../pages/BControlPage.vue'
import BRecordsPage from '../pages/BRecordsPage.vue'

const host = useHost()
</script>

<template>
  <!-- 监控页 -->
  <view class="page" :class="{ 'is-current': host.page === 'monitor' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <svg width="16" height="13" viewBox="0 0 16 13" fill="none"><path d="M2 11V6L6 2h6l2 3v6h-3V8H5v3z" fill="currentColor"/><rect x="6" y="4" width="2" height="2" style="fill:var(--surface-card)"/></svg>
        <text class="qh-menubar__ttl">果园守护</text>
        <text class="qh-menubar__item">文件</text>
        <text class="qh-menubar__item">监测</text>
        <text class="qh-menubar__item">告警</text>
        <text class="qh-menubar__item">特效</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content">
      <BMonitorPage />
    </view>
  </view>

  <!-- 告警页 -->
  <view class="page" :class="{ 'is-current': host.page === 'alarms' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <svg width="16" height="13" viewBox="0 0 16 13" fill="none"><path d="M2 11V6L6 2h6l2 3v6h-3V8H5v3z" fill="currentColor"/><rect x="6" y="4" width="2" height="2" style="fill:var(--surface-card)"/></svg>
        <text class="qh-menubar__ttl">果园守护</text>
        <text class="qh-menubar__item">文件</text>
        <text class="qh-menubar__item">监测</text>
        <text class="qh-menubar__item">告警</text>
        <text class="qh-menubar__item">特效</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><BAlarmsPage /></view>
  </view>

  <!-- 控制页 -->
  <view class="page" :class="{ 'is-current': host.page === 'control' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <svg width="16" height="13" viewBox="0 0 16 13" fill="none"><path d="M2 11V6L6 2h6l2 3v6h-3V8H5v3z" fill="currentColor"/><rect x="6" y="4" width="2" height="2" style="fill:var(--surface-card)"/></svg>
        <text class="qh-menubar__ttl">果园守护</text>
        <text class="qh-menubar__item">文件</text>
        <text class="qh-menubar__item">监测</text>
        <text class="qh-menubar__item">告警</text>
        <text class="qh-menubar__item">特效</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><BControlPage /></view>
  </view>

  <!-- 记录页 -->
  <view class="page" :class="{ 'is-current': host.page === 'records' }">
    <view class="statusbar">
      <view class="qh-menubar">
        <svg width="16" height="13" viewBox="0 0 16 13" fill="none"><path d="M2 11V6L6 2h6l2 3v6h-3V8H5v3z" fill="currentColor"/><rect x="6" y="4" width="2" height="2" style="fill:var(--surface-card)"/></svg>
        <text class="qh-menubar__ttl">果园守护</text>
        <text class="qh-menubar__item">文件</text>
        <text class="qh-menubar__item">监测</text>
        <text class="qh-menubar__item">告警</text>
        <text class="qh-menubar__item">特效</text>
        <view class="qh-menubar__right"><text class="time">9:41</text></view>
      </view>
    </view>
    <view class="page__content"><BRecordsPage /></view>
  </view>

  <!-- dock:五个语义入口 -->
  <view class="qh-tabbar">
    <view class="qh-tabbar__pill">
      <button class="qh-tab" :class="{ 'is-active': host.page === 'monitor' }" @click="host.nav('monitor')">
        <svg width="19" height="19" viewBox="0 0 19 19" fill="none"><path d="M1.5 9.5C3.5 5.5 6.3 3.5 9.5 3.5s6 2 8 6c-2 4-4.8 6-8 6s-6-2-8-6z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><circle cx="9.5" cy="9.5" r="2.5" fill="currentColor"/></svg>
        <text>监控</text>
      </button>
      <button class="qh-tab" :class="{ 'is-active': host.page === 'alarms' }" @click="host.nav('alarms')">
        <svg width="19" height="19" viewBox="0 0 19 19" fill="none"><path d="M9.5 2.5a5 5 0 015 5v3l1.5 2.5h-13L4.5 10.5v-3a5 5 0 015-5z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M7.8 15.5a1.8 1.8 0 003.4 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        <text class="qh-tab__labelrow">告警<text v-if="host.s?.counts.pending" class="qh-tab__badge">{{ host.s.counts.pending }}</text></text>
      </button>
      <button class="qh-tab" :class="{ 'is-active': host.page === 'control' }" @click="host.nav('control')">
        <svg width="19" height="19" viewBox="0 0 19 19" fill="none"><path d="M9.5 2v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M5.2 4.8a7 7 0 108.6 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        <text>控制</text>
      </button>
      <button class="qh-tab" :class="{ 'is-active': host.page === 'records' }" @click="host.nav('records')">
        <svg width="19" height="19" viewBox="0 0 19 19" fill="none"><rect x="2.5" y="3" width="14" height="4" rx="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M4 7v7a2 2 0 002 2h7a2 2 0 002-2V7M7.5 10.5h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        <text>记录</text>
      </button>
      <button class="qh-tab" :class="{ 'is-active': host.page === 'me' || host.page === 'themes' || host.page === 'analytics' }" @click="host.nav('me')">
        <svg width="19" height="19" viewBox="0 0 19 19" fill="none"><circle cx="9.5" cy="6.5" r="3.5" stroke="currentColor" stroke-width="1.5"/><path d="M3 16.5c1-3.5 3.4-5 6.5-5s5.5 1.5 6.5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        <text>我的</text>
      </button>
    </view>
  </view>
</template>
