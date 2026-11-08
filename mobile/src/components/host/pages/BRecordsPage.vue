<script setup lang="ts">
// B 主题记录页:平移;筛选/回看任务由 Host 持有(切主题保留)
import { useHost, time } from '../hostContext'
import VideoLibrary from '../../VideoLibrary.vue'

const host = useHost()
</script>

<template>
  <view class="qh-header__brand">
    <text class="qh-page-title">检测档案</text>
    <text class="qh-page-subtitle">按视频回看，按鸟类查找</text>
  </view>
  <view class="qh-seg">
    <view class="qh-seg__item" :class="{ 'is-active': host.recordMode === 'videos' }" @click="host.recordMode = 'videos'">视频与鸟类</view>
    <view class="qh-seg__item" :class="{ 'is-active': host.recordMode === 'actions' }" @click="host.recordMode = 'actions'">处理操作记录</view>
  </view>
  <VideoLibrary v-if="host.recordMode === 'videos'" :key="host.archiveNonce" :initial-task="host.archiveTask" :initial-time="host.archiveTime" />
  <template v-else>
    <view class="qh-stats">
      <view class="qh-stat"><text class="qh-stat__num">{{ host.s?.counts.total || 0 }}</text><text class="qh-stat__label">检测事件</text></view>
      <view class="qh-stat"><text class="qh-stat__num">{{ host.s?.counts.completed || 0 }}</text><text class="qh-stat__label">模拟执行完成</text></view>
    </view>
    <view class="qh-seg">
      <view v-for="it in [{id:'all',name:'全部记录'},{id:'detection',name:'检测事件'},{id:'actions',name:'处理操作'}]" :key="it.id" class="qh-seg__item" :class="{ 'is-active': host.recordFilter === it.id }" @click="host.recordFilter = it.id">{{ it.name }}</view>
    </view>
    <view v-for="ev in host.events" :key="ev.id" class="qh-card" style="cursor:pointer" @click="host.run(() => host.inspectEvent(ev))">
      <text class="qh-tl__title">{{ ev.message }}</text>
      <text class="qh-tl__msg">{{ time(ev.at) }} · {{ ev.ref_id }}</text>
    </view>
    <view v-if="!host.events.length" style="padding:40px 0;text-align:center"><text class="qh-note">开始巡护，留下第一条记录</text></view>
    <button v-if="!host.historyEnd && ((host.s?.events.length || 0) >= 100 || host.older.length)" class="qh-btn qh-btn--secondary qh-btn--sm" style="width:100%" :disabled="host.store.busy" @click="host.run(host.loadHistory)">加载更早记录</button>
  </template>
</template>
