<script setup lang="ts">
import { useHost, names, clock, shortTime, time, alarmClass } from '../host/hostContext'

const host = useHost()
</script>
<template>
  <view class="hd"><text class="b">告警挂牌</text><text class="s">待人工确认 · {{ host.s?.counts.pending || 0 }} 条</text></view>
  <view class="tags">
    <view v-for="(a, i) in host.pending.slice(0, 6)" :key="a.id" class="tag hot" style="cursor:pointer" @click="host.openAlarm(a)">
      <text class="tag-name">{{ a.species }}</text>
      <text class="tag-meta mono">×{{ a.count }} · {{ Math.round(a.confidence * 100) }}% · {{ shortTime(a.at) }}</text>
      <text class="tag-st">待处理</text>
      <view v-if="i === 0" class="tag-actions" @click.stop>
        <text class="ta main" @click.stop="host.quickRepel(a.id)">▶ 升旗驱离</text>
        <text class="ta" @click.stop="host.run(() => host.requestIgnore(a.id))">忽略</text>
      </view>
    </view>
    <view v-if="!host.pending.length" class="tag empty"><text class="tag-name">无进行中告警</text><text class="tag-meta">历史见「记录」页</text></view>
  </view>
  <view class="hd" style="margin-top:10px"><text class="b">历史记录</text><text class="s">已处理/已忽略</text></view>
  <view class="tags">
    <view v-for="a in (host.s?.alarms || []).filter(a => a.status !== 'new').slice(0, 4)" :key="a.id" class="tag" style="cursor:pointer" @click="host.openAlarm(a)">
      <text class="tag-name">{{ a.species }}</text>
      <text class="tag-meta mono">×{{ a.count }} · {{ shortTime(a.at) }}</text>
      <text class="tag-st dim">{{ names(a.status) }}</text>
    </view>
  </view>
</template>
<style scoped>
.hd{display:flex;justify-content:space-between;align-items:center;padding:14px 16px 10px}.hd .b{font-size:16px;font-weight:900;letter-spacing:2px;color:var(--ink-900)}.hd .s{font-size:9px;color:var(--ink-400,#6f6f68)}
.tags{display:flex;gap:10px;padding:0 16px;flex-wrap:wrap}
.tag{flex:1;min-width:100px;background:#fbfaf4;border:2px solid #191919;padding:14px 8px 9px;text-align:center;box-shadow:3px 4px 0 rgba(25,25,25,.22);position:relative;display:flex;flex-direction:column;gap:3px;align-items:center}
.tag::before{content:'';position:absolute;left:50%;top:-2px;transform:translateX(-50%);width:9px;height:9px;border-radius:50%;background:var(--surface-card);border:2px solid #191919}
.tag-name{font-size:13px;font-weight:900}
.tag-meta{font-size:8.5px;color:var(--ink-400)}
.tag-st{font-size:9.5px;font-weight:900;border:2px solid #191919;padding:1px 7px;transform:rotate(-3deg)}
.tag.hot .tag-st{background:var(--warn-bg);border-color:var(--warn-bg);color:#fff}
.tag-st.dim{border-color:var(--ink-400);color:var(--ink-400)}
.tag.empty{border-style:dashed;color:var(--ink-400)}

.tag-actions{display:flex;gap:5px;margin-top:6px;width:100%}
.ta{flex:1;border:2px solid #191919;font-size:10px;font-weight:900;text-align:center;padding:5px 0;color:#191919;cursor:pointer}
.ta.main{background:var(--warn-bg);border-color:var(--warn-bg);color:var(--warn-fg)}
</style>