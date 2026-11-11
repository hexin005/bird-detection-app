<script setup lang="ts">
// B 主题记录页(一检一记):统计条 + 检测档案卡(方案 A)。
// 事件流水/指令链不再在此展示——执行链收进卡片展开详情与告警/操作记录弹窗;
// 旧「巡逻日志/视频档案」双段由 DetectionRecords 承接,VideoLibrary 仍被 Tower/Pixel 回落页引用。
import { useHost } from '../hostContext'
import DetectionRecords from '../DetectionRecords.vue'

const host = useHost()
</script>

<template>
  <view class="qh-header__brand">
    <text class="qh-page-title">检测记录</text>
    <text class="qh-page-subtitle">一次检测 = 一条记录 · 只看时间与结果</text>
  </view>
  <view class="rec-stats">
    <view class="rec-stat"><text class="n">{{ host.recordsSummary?.today_tasks ?? 0 }}</text><text class="l">今日检测</text></view>
    <view class="rec-stat"><text class="n">{{ host.recordsSummary?.birds_total ?? 0 }}</text><text class="l">发现鸟数</text></view>
    <view class="rec-stat"><text class="n">{{ host.s?.counts.completed || 0 }}</text><text class="l">驱离完成</text></view>
  </view>
  <DetectionRecords :initial-task="host.archiveTask" :nonce="host.archiveNonce" />
</template>

<style scoped>
/* 统计条:三格合并横排(沿用旧版样式) */
.rec-stats{display:flex;margin:6px 14px 4px;border:2px solid var(--ink-900);background:var(--surface-card);box-shadow:4px 4px 0 var(--shadow-ink)}
.rec-stat{flex:1;text-align:center;padding:9px 0 7px;border-right:1px solid var(--line)}
.rec-stat:last-child{border-right:none}
.rec-stat .n{display:block;font-size:19px;font-weight:800;font-family:var(--font-num);line-height:1.1}
.rec-stat .l{display:block;font-size:10px;color:var(--ink-400);letter-spacing:2px;margin-top:2px}
</style>
