<script setup lang="ts">
import { useHost, names, clock, shortTime, time, alarmClass } from '../host/hostContext'

const host = useHost()
</script>
<template>
  <view class="hd"><text class="b">观测档案</text><text class="s">按视频回看 · 按鸟类查找</text></view>
  <view v-for="a in (host.s?.alarms || []).slice(0, 6)" :key="a.id" class="arc" style="cursor:pointer" @click="host.openAlarm(a)">
    <i class="play">▶</i>
    <view class="info"><text class="nm">{{ a.species }} · 检测片段</text><text class="meta mono">{{ shortTime(a.at) }} · {{ a.video_time.toFixed(1) }}s · {{ Math.round(a.confidence * 100) }}%</text></view>
    <text class="st">{{ names(a.status) }}</text>
  </view>
  <view v-if="!(host.s?.alarms || []).length" class="empty">暂无检测档案</view>
  <view class="hd" style="margin-top:10px"><text class="b">物种索引</text><text class="s">自动建立</text></view>
  <view style="display:flex;flex-wrap:wrap;gap:6px;padding:0 16px">
    <text v-for="sp in [...new Set((host.s?.alarms || []).map(a => a.species))]" :key="sp" class="sp-tag">{{ sp }}</text>
  </view>
  <view v-if="!(host.s?.alarms || []).length" class="empty" style="padding:20px">暂无数据</view>
</template>
<style scoped>
.hd{display:flex;justify-content:space-between;align-items:center;padding:14px 16px 10px}.hd .b{font-size:16px;font-weight:900;letter-spacing:2px;color:var(--ink-900)}.hd .s{font-size:9px;color:var(--grey)}
.arc{display:flex;align-items:center;gap:10px;margin:0 16px 10px;border:2px solid #191919;background:#fbfaf4;box-shadow:3px 4px 0 rgba(25,25,25,.22);padding:10px;cursor:pointer}
.play{width:36px;height:36px;flex-shrink:0;border:2px solid #191919;display:flex;align-items:center;justify-content:center;font-size:14px;font-style:normal}
.info{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.nm{font-size:12px;font-weight:900}
.meta{font-size:9px;color:var(--grey)}
.st{font-size:9px;font-weight:900;border:2px solid #191919;padding:2px 6px;color:#191919;flex-shrink:0}
.empty{text-align:center;padding:20px;font-size:10px;color:var(--grey)}
.sp-tag{border:1px solid #191919;font-size:10px;padding:2px 6px;color:#191919}
</style>