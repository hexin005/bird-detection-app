<script setup lang="ts">
// B 主题监控页:自 index.vue 平移,业务状态/动作来自 HostContext(零行为变化)
import { useHost, badgeText, monClass, shortTime } from '../hostContext'
import VideoWorkspace from '../../VideoWorkspace.vue'

const host = useHost()
</script>

<template>
  <view class="qh-header">
    <view class="qh-header__brand">
      <view class="qh-header__row"><text class="qh-appname">青禾示范果园</text><text class="qh-mvp">MVP</text></view>
      <text class="qh-site">东区 · 01 号监控点</text>
    </view>
    <view class="qh-header__actions">
      <button class="qh-3dbtn" @click="host.openScene"><text>3D 视角</text></button>
      <button class="qh-iconbtn" @click="host.settings"><svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.5"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33h.01a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51h.01a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82v.01a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z" stroke="currentColor" stroke-width="1.5"/></svg></button>
    </view>
  </view>

  <view class="qh-conn"><view class="qh-conn__left"><view class="qh-conn__dot"/><text>{{ host.store.connection }}</text></view><text class="qh-conn__src">{{ host.s ? '数据来自果园服务' : '等待同步' }}</text></view>

  <view class="qh-titleblock">
    <view class="qh-titlerow">
      <text class="qh-page-title">果园，尽在掌握</text>
      <view :class="monClass(host.s?.monitor.status || 'idle')"><view class="qh-badge__dot"/><text class="qh-badge__text">{{ badgeText(host.s?.monitor.status || 'idle') }}</text></view>
    </view>
    <text class="qh-page-subtitle">今日巡护，从这里开始</text>
  </view>

  <VideoWorkspace />

  <view class="qh-stats">
    <view class="qh-stat"><text class="qh-stat__num qh-stat__num--warn">{{ host.s?.counts.pending || 0 }}</text><text class="qh-stat__label">待处理告警</text></view>
    <view class="qh-stat"><text class="qh-stat__num">{{ host.s?.counts.total || 0 }}</text><text class="qh-stat__label">检测事件</text></view>
    <view class="qh-stat"><text class="qh-stat__num">{{ host.s?.counts.completed || 0 }}</text><text class="qh-stat__label">模拟执行完成</text></view>
  </view>

  <view v-if="host.pending.length" class="qh-card qh-alarmcard" style="cursor:pointer" @click="host.openAlarm(host.pending[0])">
    <view class="qh-alarmcard__top">
      <image class="qh-thumb" :src="host.store.media('captures/' + host.pending[0].snapshot)" mode="aspectFill"/>
      <view class="qh-alarmcard__mid">
        <view class="qh-alarmcard__titlerow"><text class="qh-alarmcard__title">发现 {{ host.pending[0].count }} 只{{ host.pending[0].species }}</text><text class="qh-badge qh-badge--new">待处理</text></view>
        <text class="qh-alarmcard__meta">东区 · 01 号监控点 · {{ shortTime(host.pending[0].at) }}</text>
      </view>
    </view>
    <view class="qh-alarmcard__bottom">
      <text class="qh-alarmcard__stat">录像 {{ host.pending[0].video_time.toFixed(1) }} 秒 · 置信度 {{ (host.pending[0].confidence * 100).toFixed(0) }}%</text>
      <text class="qh-link">查看并处理 <text class="qh-chevron">›</text></text>
    </view>
  </view>

  <view class="qh-devicebar">
    <view class="qh-devicebar__icon"><svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M2.5 7v4h3l4 3.5v-11L5.5 7h-3z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M12 6.5a3.5 3.5 0 010 5M14 4.5a6.3 6.3 0 010 9" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg></view>
    <view class="qh-devicebar__info"><text class="qh-devicebar__name">声学驱鸟器 01</text><text class="qh-devicebar__desc">模拟设备 · 人工确认后执行</text></view>
    <view class="qh-pill"><view class="qh-pill__dot"/><text class="qh-pill__text">{{ host.offline ? '离线' : '在线' }}</text></view>
  </view>
</template>
