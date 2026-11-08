<script setup lang="ts">
// B 主题控制页:平移;模式/时长/关联告警由 Host 持有(切主题保留)
import { useHost, names } from '../hostContext'
import type { RepelMode } from '../hostContext'

const host = useHost()
</script>

<template>
  <view class="qh-header">
    <view class="qh-header__row">
      <text class="qh-page-title">远程控制</text>
      <text class="qh-badge qh-badge--new">模拟执行</text>
    </view>
  </view>

  <view class="qh-devicecard">
    <view class="qh-orbit">
      <view class="qh-orbit__ring"/>
      <view class="qh-orbit__core"><svg width="22" height="22" viewBox="0 0 18 18" fill="none"><path d="M2.5 7v4h3l4 3.5v-11L5.5 7h-3z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M12 6.5a3.5 3.5 0 010 5M14 4.5a6.3 6.3 0 010 9" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg></view>
      <svg class="qh-orbit__wave" style="left:2px;" width="14" height="20" viewBox="0 0 14 20" fill="none"><path d="M11 3Q4 10 11 17M7 6.5Q3.5 10 7 13.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      <svg class="qh-orbit__wave" style="right:2px;" width="14" height="20" viewBox="0 0 14 20" fill="none"><path d="M3 3Q10 10 3 17M7 6.5Q10.5 10 7 13.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      <view class="qh-orbit__dot"/>
    </view>
    <view class="qh-devicerow">
      <text class="qh-devicename">{{ host.activeMode.name }}</text>
      <view class="qh-pill"><view class="qh-pill__dot"/><text class="qh-pill__text">{{ host.offline ? '离线' : '在线' }}</text></view>
    </view>
    <text class="qh-devicecode">{{ host.activeMode.code }}</text>
    <view v-if="host.selectedAlarm" class="qh-linkstrip">
      <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M5.5 7.5a3 3 0 004.2 0l1.8-1.8a3 3 0 00-4.2-4.2L6.2 2.6M7.5 5.5a3 3 0 00-4.2 0L1.5 7.3a3 3 0 004.2 4.2l1.1-1.1" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
      <text class="qh-linkstrip__text">关联告警 {{ host.selectedAlarm }}</text>
      <text class="qh-linkstrip__cancel" @click="host.selectedAlarm = null">取消关联</text>
    </view>
  </view>

  <view class="qh-durcard">
    <view class="qh-durcard__top"><text class="qh-durcard__label">驱离方式</text><text class="qh-durcard__note">红外与声学可双模联动</text></view>
    <view class="qh-duropts">
      <view v-for="m in [{ id:'acoustic', name:'声波' }, { id:'infrared', name:'红外' }, { id:'both', name:'双模联动' }]" :key="m.id" class="qh-duropt" :class="{ 'is-selected': host.mode === m.id }" @click="host.mode = m.id as RepelMode">{{ m.name }}</view>
    </view>
  </view>

  <view class="qh-durcard">
    <view class="qh-durcard__top"><text class="qh-durcard__label">单次执行时长</text><text class="qh-durcard__note">定时结束 · 不连续运行</text></view>
    <view class="qh-duropts">
      <view v-for="d in [3,5,8]" :key="d" class="qh-duropt" :class="{ 'is-selected': host.duration === d }" @click="host.duration = d">{{ d }} 秒</view>
    </view>
  </view>

  <view v-if="host.store.active" class="qh-card">
    <view class="qh-resultcard" style="padding:0;background:transparent">
      <view class="qh-resultcard__info grow"><text class="qh-resultcard__title">{{ names(host.store.active.status) }}</text><text class="qh-resultcard__desc">{{ host.store.active.message }}</text></view>
      <text class="qh-paramrow__value" style="font-family:var(--font-num)">{{ host.remaining }}s</text>
    </view>
    <view class="qh-progress" style="margin-top:10px"><view class="qh-progress__bar" :style="{ width: (host.store.active.status === 'pending' ? 0 : Math.min(100, (1 - host.remaining / host.store.active.duration) * 100)) + '%' }"/></view>
    <button class="qh-btn qh-btn--ghost-danger" style="width:100%;margin-top:10px;border:1px solid var(--line-strong);min-height:40px;font-size:var(--text-md);color:var(--danger-fg)" :disabled="host.store.busy" @click="host.run(() => host.store.mutate('/commands/' + host.store.active!.id + '/stop'))">停止本次执行</button>
  </view>

  <view v-else-if="host.s?.commands[0]" class="qh-resultcard" style="cursor:pointer" @click="host.detailId = host.s.commands[0].id; host.modal = 'mLog'">
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="7.5" stroke="currentColor" stroke-width="1.5"/><path d="M5.8 9.2l2.2 2.2 4.2-4.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
    <view class="qh-resultcard__info"><text class="qh-resultcard__title">最近一次执行 · {{ names(host.s.commands[0].status) }}</text><text class="qh-resultcard__desc">{{ host.s.commands[0].message }}</text></view>
  </view>

  <button class="qh-btn qh-btn--primary" :disabled="host.store.busy || host.offline || !!host.store.active" @click="host.modal = 'mConfirm'">
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><path d="M2 5.5v4h2.5L8 12.5v-10L4.5 5.5H2z" fill="currentColor"/><path d="M10.5 5a3.5 3.5 0 010 5M12.5 3a6.5 6.5 0 010 9" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>{{ host.offline ? '设备离线，无法执行' : '执行一次驱离' }}
  </button>

  <text class="qh-note">本设备是模拟执行器，不会控制真实硬件</text>
  <view class="qh-shortcut" @click="host.settings">
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><rect x="1" y="1" width="4.6" height="4.6" rx="1" stroke="currentColor" stroke-width="1.3"/><rect x="7.4" y="1" width="4.6" height="4.6" rx="1" stroke="currentColor" stroke-width="1.3"/><rect x="1" y="7.4" width="4.6" height="4.6" rx="1" stroke="currentColor" stroke-width="1.3"/><rect x="7.4" y="7.4" width="4.6" height="4.6" rx="1" stroke="currentColor" stroke-width="1.3"/></svg>
    <text>切换离线 / 超时演示场景</text>
  </view>
</template>
