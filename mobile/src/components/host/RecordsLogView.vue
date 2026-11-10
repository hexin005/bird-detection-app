<script setup lang="ts">
// R1 巡逻日志共享组件:按日分组 + 指令链归并(确认→执行→回执合并为组)。
// 四主题记录页复用;观感走主题 token。
import { computed } from 'vue'
import { useHost, names, clock, type EventGroup } from './hostContext'

const host = useHost()

/** 日桶:组按天再聚合,今天标注"今天" */
const dayBuckets = computed(() => {
  const buckets: { label: string; today: boolean; groups: EventGroup[] }[] = []
  for (const g of host.groupedEvents) {
    const last = buckets[buckets.length - 1]
    if (last && last.label === g.day) last.groups.push(g)
    else buckets.push({ label: g.day, today: g.today, groups: [g] })
  }
  return buckets
})

const groupIcon = (g: EventGroup) => (g.kind === 'command' ? '▶' : g.kind === 'detection' ? '♦' : g.kind === 'ignored' ? '✕' : '⚡')
async function inspectGroup(g: EventGroup) {
  if (g.kind === 'detection' || g.kind === 'command') {
    const probe = g.kind === 'command' ? { id: 0, kind: 'command', ref_id: g.ref, at: g.at, message: '' } : g.lines[0]
    await host.inspectEvent(probe)
  }
}
</script>

<template>
  <template v-for="bucket in dayBuckets" :key="bucket.label">
    <view class="rl-daybar"><text>{{ bucket.label }}<text v-if="bucket.today" class="today"> · 今天</text></text></view>
    <template v-for="g in bucket.groups" :key="g.key">
      <!-- 指令链:标题 + 时间线 -->
      <view v-if="g.kind === 'command'" class="rl-chain" @click="inspectGroup(g)">
        <view class="rl-chain__hd">
          <text class="rl-blk fill">{{ groupIcon(g) }}</text>
          <view class="mid">
            <text class="t">{{ g.title }}</text>
            <text v-if="g.autoMsg" class="s mono">{{ g.autoMsg }}</text>
          </view>
          <text class="qh-badge qh-badge--ended">{{ names(g.status || 'pending') }}</text>
        </view>
        <view class="rl-chain__lines mono">
          <view v-for="l in g.lines" :key="l.id" class="rl-line">
            <text class="tm">{{ clock(l.at) }}</text><text class="msg">{{ l.message }}</text>
          </view>
        </view>
      </view>
      <!-- 单行:检测 / 忽略 / 自动跳过 -->
      <view v-else class="rl-row" @click="g.kind === 'detection' && inspectGroup(g)">
        <text class="rl-blk" :class="{ dash: g.kind === 'ignored' }">{{ groupIcon(g) }}</text>
        <text class="rl-row__t" :class="{ click: g.kind === 'detection' }">{{ g.title }}</text>
        <text class="rl-row__tm mono">{{ clock(g.at) }}</text>
      </view>
    </template>
  </template>
  <view v-if="!host.groupedEvents.length" class="rl-empty"><text class="qh-note">开始巡护，留下第一条记录</text></view>
  <button v-if="!host.historyEnd && ((host.s?.events.length || 0) >= 100 || host.older.length)" class="qh-btn qh-btn--secondary qh-btn--sm rl-more" :disabled="host.store.busy" @click="host.run(host.loadHistory)">加载更早记录</button>
</template>

<style scoped>
/* 日分隔 */
.rl-daybar{display:flex;align-items:center;gap:10px;margin:16px 14px 8px;font-size:11px;font-weight:800;letter-spacing:2px;color:var(--ink-400)}
.rl-daybar::before,.rl-daybar::after{content:"";flex:1;height:2px;background:var(--ink-900)}
.rl-daybar .today{color:var(--accent)}
/* 指令链组 */
.rl-chain{margin:0 14px 10px;border:2px solid var(--ink-900);background:var(--surface-card);box-shadow:4px 4px 0 var(--shadow-ink);cursor:pointer}
.rl-chain__hd{display:flex;align-items:center;gap:10px;padding:10px 12px;border-bottom:2px solid var(--ink-900)}
.rl-chain__hd .mid{flex:1;min-width:0}
.rl-chain__hd .t{display:block;font-size:13px;font-weight:800;color:var(--ink-900)}
.rl-chain__hd .s{display:block;font-size:9px;color:var(--ink-400);margin-top:2px;letter-spacing:1px}
.rl-chain__lines{padding:7px 12px 8px}
.rl-line{display:flex;gap:10px;padding:2px 0;font-size:11px}
.rl-line .tm{color:var(--ink-400);flex-shrink:0}
.rl-line .msg{color:var(--ink-700)}
/* 单行事件 */
.rl-row{display:flex;align-items:center;gap:10px;margin:0 14px 10px;padding:9px 12px;border:2px solid var(--ink-900);background:var(--surface-card);box-shadow:4px 4px 0 var(--shadow-ink);cursor:pointer}
.rl-row__t{flex:1;font-size:12.5px;font-weight:600;color:var(--ink-900);min-width:0}
.rl-row__t.click{font-weight:800}
.rl-row__tm{font-size:11px;color:var(--ink-400);flex-shrink:0}
/* 类型方块 */
.rl-blk{display:inline-flex;width:26px;height:26px;border:2px solid var(--ink-900);align-items:center;justify-content:center;font-size:12px;flex-shrink:0;color:var(--ink-900);background:var(--surface-card)}
.rl-blk.fill{background:var(--ink-900);color:var(--surface-card)}
.rl-blk.dash{border-style:dashed}
.rl-empty{padding:30px 0 10px;text-align:center}
.rl-more{width:calc(100% - 28px);margin:4px 14px 10px}
</style>
