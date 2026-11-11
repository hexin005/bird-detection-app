<script setup lang="ts">
// C 记录页「观测时间轴」:只记鸟情发现(不含执行日志),按日分组;
// 底部入口页内切换进视频档案(复用 VideoLibrary 的按视频/按鸟类检索)。
// 置信度/数量等从快照 alarms 按 ref_id 补全,取不到时退化为事件文本。
import { computed, ref, watch } from 'vue'
import { useHost, clock } from '../host/hostContext'
import VideoLibrary from '../VideoLibrary.vue'
import type { Alarm } from '../../types'

const host = useHost()
const view = ref<'timeline' | 'archive'>(host.archiveTask ? 'archive' : 'timeline')
// 告警回放等深链携带 archiveTask 进入时,自动落在档案视图
watch(() => host.archiveTask, task => { if (task) view.value = 'archive' })
function openArchive() { view.value = 'archive' }
function backTimeline() { view.value = 'timeline' }

type TimelineRow = { key: string; at: number; message: string; ref: string; alarm?: Alarm }
type DayBucket = { label: string; today: boolean; rows: TimelineRow[] }
function alarmOf(refId: string): Alarm | undefined {
  return host.s?.alarms.find(a => a.id === refId)
}
/** 只保留检测发现,按日分组(共用 groupedEvents 的归并结果,不含指令链/忽略/自动化) */
const days = computed<DayBucket[]>(() => {
  const buckets: DayBucket[] = []
  for (const g of host.groupedEvents) {
    if (g.kind !== 'detection') continue
    const row: TimelineRow = { key: g.key, at: g.at, message: g.title, ref: g.ref, alarm: alarmOf(g.ref) }
    const last = buckets[buckets.length - 1]
    if (last && last.label === g.day) last.rows.push(row)
    else buckets.push({ label: g.day, today: g.today, rows: [row] })
  }
  return buckets
})
function openRow(ref: string, at: number) {
  void host.inspectEvent({ id: 0, kind: 'detection', ref_id: ref, at, message: '' })
}
</script>

<template>
  <!-- ===== 视图一:观测时间轴 ===== -->
  <template v-if="view === 'timeline'">
    <view class="tl-head">
      <view class="tl-title"><text class="tl-big">观测时间轴</text><text class="tl-tag">TIMELINE</text></view>
      <view class="tl-vol"><text>ST.01 东区</text><text>发现即记录</text></view>
    </view>
    <view class="tl-strip">
      <view><text class="n mono">{{ host.recordsSummary?.today_tasks ?? '—' }}</text><text class="l">今日检测</text></view>
      <view><text class="n mono">{{ host.recordsSummary?.tasks_total ?? '—' }}</text><text class="l">累计档案</text></view>
    </view>

    <template v-for="d in days" :key="d.label">
      <view class="tl-day" :class="{ grey: !d.today }"><i class="sq"/><text class="d">{{ d.label }}<text v-if="d.today"> · 今天</text></text><i class="ln"/><text class="n2">{{ d.rows.length }} 次发现</text></view>
      <view class="tl-list">
        <view v-for="r in d.rows" :key="r.key" class="tl-ev" @click="openRow(r.ref, r.at)">
          <view class="r1">
            <text class="sp">{{ r.alarm ? r.alarm.species : '鸟类发现' }}</text>
            <text v-if="r.alarm" class="x mono">×{{ r.alarm.count }}</text>
            <i class="play">▶</i>
          </view>
          <text v-if="!r.alarm" class="msg">{{ r.message }}</text>
          <view class="meta"><text class="mono">{{ clock(r.at) }}</text><text v-if="r.alarm">{{ r.alarm.site }}</text><text v-if="r.alarm">片段 {{ r.alarm.video_time.toFixed(1) }} 秒起</text></view>
          <view v-if="r.alarm" class="conf"><view class="track"><i :style="{ width: Math.round(r.alarm.confidence * 100) + '%' }"/></view><text class="mono cv">{{ Math.round(r.alarm.confidence * 100) }}%</text></view>
        </view>
      </view>
    </template>
    <view v-if="!days.length" class="tl-empty"><text class="qh-note">暂无鸟情发现 · 开始观测后按日记录在这里</text></view>
    <button v-if="!host.historyEnd && ((host.s?.events.length || 0) >= 100 || host.older.length)" class="qh-btn qh-btn--secondary qh-btn--sm tl-more" :disabled="host.store.busy" @click="host.run(host.loadHistory)">加载更早发现</button>

    <view class="tl-librow" @click="openArchive"><text>打开视频档案<text v-if="host.recordsSummary?.tasks_total != null"> · {{ host.recordsSummary.tasks_total }} 卷</text></text><text class="sub">按视频 / 按鸟类检索 ›</text></view>
    <text class="tl-note">时间轴只记鸟情发现，驱离操作以信号台播报为准 · 点卡片回看检测片段</text>
  </template>

  <!-- ===== 视图二:视频档案(页内切换,复用 VideoLibrary) ===== -->
  <template v-else>
    <view class="tl-backrow" @click="backTimeline"><text class="bk">◂ 返回时间轴</text><text class="sub2">视频档案<text v-if="host.recordsSummary?.tasks_total != null"> · {{ host.recordsSummary.tasks_total }} 卷</text></text></view>
    <VideoLibrary :key="host.archiveNonce" :initial-task="host.archiveTask" :initial-time="host.archiveTime" />
  </template>
</template>

<style scoped>
/* ===== 头部 ===== */
.tl-head{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:14px 16px 10px}
.tl-title{display:flex;align-items:center;gap:8px}
.tl-big{font-size:19px;font-weight:900;letter-spacing:3px;color:var(--ink-900)}
.tl-tag{background:#f5c400;border:2px solid var(--ink-900);color:var(--ink-900);font-size:9px;font-weight:900;letter-spacing:2px;padding:3px 8px;box-shadow:2px 2px 0 var(--shadow-ink)}
.tl-vol{display:flex;flex-direction:column;align-items:flex-end;gap:2px}
.tl-vol text{font-size:9px;color:var(--ink-400);letter-spacing:1px}
/* 统计带 */
.tl-strip{display:flex;border:2px solid var(--ink-900);background:var(--surface-card);margin:0 14px}
.tl-strip>view{flex:1;text-align:center;padding:9px 0 8px;border-right:2px solid var(--ink-900);display:flex;flex-direction:column;gap:2px}
.tl-strip>view:last-child{border-right:0}
.tl-strip .n{font-size:19px;font-weight:700;color:var(--ink-900)}
.tl-strip .l{font-size:8.5px;letter-spacing:2px;color:var(--ink-400);font-weight:700}
/* 日分隔 */
.tl-day{display:flex;align-items:center;gap:8px;margin:16px 14px 10px}
.tl-day .sq{width:14px;height:14px;background:#d3212c;border:2px solid var(--ink-900)}
.tl-day.grey .sq{background:var(--surface-card)}
.tl-day .d{font-size:12px;font-weight:900;letter-spacing:2px;color:var(--ink-900);white-space:nowrap}
.tl-day .ln{flex:1;height:2px;background:var(--ink-900)}
.tl-day .n2{font-size:9px;color:var(--ink-400);white-space:nowrap}
/* 时间轴:胶片孔 + 事件卡 */
.tl-list{position:relative;margin:0 14px;padding-left:26px}
.tl-list::before{content:'';position:absolute;left:8px;top:2px;bottom:2px;width:8px;
  background-image:repeating-linear-gradient(180deg,var(--surface-canvas) 0 10px,var(--ink-900) 10px 14px);border:2px solid var(--ink-900)}
.tl-ev{position:relative;border:2px solid var(--ink-900);background:var(--surface-card);box-shadow:3px 3px 0 var(--shadow-ink);margin-bottom:10px;padding:9px 11px;cursor:pointer}
.tl-ev::before{content:'';position:absolute;left:-24px;top:14px;width:10px;height:10px;background:#f5c400;border:2px solid var(--ink-900)}
.tl-ev .r1{display:flex;align-items:center;gap:8px;min-width:0}
.tl-ev .sp{font-size:13px;font-weight:900;color:var(--ink-900);overflow-wrap:anywhere;min-width:0}
.tl-ev .x{font-size:10px;font-weight:900;background:var(--ink-900);color:#f5c400;padding:1px 6px;flex-shrink:0}
.tl-ev .play{margin-left:auto;width:24px;height:24px;flex-shrink:0;background:var(--ink-900);color:#f5c400;display:flex;align-items:center;justify-content:center;font-size:10px;font-style:normal}
.tl-ev .msg{display:block;font-size:10.5px;color:var(--ink-700);margin-top:4px}
.tl-ev .meta{display:flex;gap:8px;margin-top:5px;font-size:8.5px;color:var(--ink-400);flex-wrap:wrap}
.tl-ev .conf{display:flex;align-items:center;gap:5px;margin-top:7px}
.tl-ev .track{flex:1;height:8px;border:2px solid var(--ink-900);background:var(--surface-card)}
.tl-ev .track i{display:block;height:100%;background:#f5c400}
.tl-ev .cv{font-size:9px;font-weight:700;color:var(--ink-900)}
.tl-empty{padding:26px 0 6px;text-align:center}
.tl-more{width:calc(100% - 28px);margin:2px 14px 6px}
/* 底部档案入口 */
.tl-librow{display:flex;align-items:center;justify-content:space-between;gap:8px;border:2px solid var(--ink-900);background:var(--ink-900);color:#f5c400;margin:14px 14px 8px;padding:11px 12px;font-size:12.5px;font-weight:900;letter-spacing:2px;cursor:pointer;box-shadow:3px 3px 0 var(--shadow-ink)}
.tl-librow .sub{font-size:9px;color:#9a9a92;letter-spacing:1px;font-weight:700;white-space:nowrap}
.tl-note{display:block;font-size:9px;color:var(--ink-400);text-align:center;margin:2px 14px 12px;line-height:1.7}
/* 档案视图返回行 */
.tl-backrow{display:flex;align-items:center;gap:8px;margin:12px 14px 2px}
.tl-backrow .bk{border:2px solid var(--ink-900);background:var(--surface-card);padding:4px 9px;font-size:11px;font-weight:900;letter-spacing:1px;color:var(--ink-900);box-shadow:2px 2px 0 var(--shadow-ink);cursor:pointer}
.tl-backrow .sub2{font-size:10px;color:var(--ink-400);font-weight:700;letter-spacing:1px}
</style>
