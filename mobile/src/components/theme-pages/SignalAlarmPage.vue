<script setup lang="ts">
// C 告警「挂牌告警墙」:待处理上挂杆挂牌(牌内联驱离/忽略),执行中挂黄章牌;
// 物种筛选复用 AlarmSpeciesPicker,图鉴「查看该鸟告警」→ host.alarmSpecies 过滤直达。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useHost, names, shortTime } from '../host/hostContext'
import AlarmSpeciesPicker from '../host/AlarmSpeciesPicker.vue'
import { useOrchard } from '../../store'
import type { Alarm } from '../../types'

const host = useHost()
const store = useOrchard()
const filtered = computed(() => !!host.alarmSpecies)
const items = ref<Alarm[]>([])
const loading = ref(false)
const error = ref('')
const hasMore = ref(false)
let sequence = 0

const pending = computed(() => filtered.value ? items.value.filter(a => a.status === 'new') : host.pending)
const processing = computed(() => filtered.value
  ? items.value.filter(a => a.status === 'processing')
  : (host.s?.alarms || []).filter(a => a.status === 'processing'))
const history = computed(() => {
  const base = (host.s?.alarms || []).filter(a => a.status !== 'new' && a.status !== 'processing')
  return filtered.value ? items.value.filter(a => a.status !== 'new' && a.status !== 'processing') : base.slice(0, 4)
})
const pendingCount = computed(() => filtered.value ? pending.value.length : (host.s?.counts.pending || 0))

/** 物种筛选时按需拉全量(含历史);清除筛选回到快照 */
async function load(append = false) {
  if (!host.alarmSpecies) { items.value = []; hasMore.value = false; error.value = ''; loading.value = false; return }
  const current = ++sequence
  loading.value = true; error.value = ''
  try {
    const before = append ? items.value[items.value.length - 1]?.at : undefined
    const query = new URLSearchParams({ species: host.alarmSpecies })
    if (before !== undefined) query.set('before', String(before))
    const data = await store.request<{ items: Alarm[] }>('/alarm-list?' + query)
    if (current !== sequence) return
    items.value = append ? [...items.value, ...data.items] : data.items
    hasMore.value = data.items.length === 100
  } catch (e) {
    if (current === sequence) error.value = (e as Error).message
  } finally {
    if (current === sequence) loading.value = false
  }
}
watch(() => host.alarmSpecies, () => { ++sequence; items.value = []; void load() })
onMounted(() => { if (host.alarmSpecies) void load() })
onBeforeUnmount(() => { ++sequence })

function activeOf(a: Alarm): string {
  return host.store.active && host.store.active.alarm_id === a.id ? '信号升空 · 剩余 ' + Math.max(0, host.remaining) + 's' : '双模联挂执行中'
}
</script>

<template>
  <view class="alw-head">
    <view><text class="eyebrow">SIGNAL WALL</text><text class="title">挂牌告警墙</text></view>
    <text class="tag" :class="{ hot: pendingCount > 0 }">待处理 {{ pendingCount }}</text>
  </view>

  <!-- 图鉴跳转来的筛选提示 -->
  <view v-if="filtered" class="alw-filter">
    <text class="ft">正在查看 · {{ host.alarmSpecies }}</text>
    <text class="fc" @click="host.alarmSpecies = ''">清除筛选 ×</text>
  </view>
  <text v-if="filtered && loading && !items.length" class="alw-feedback">正在读取该鸟种告警…</text>
  <text v-if="filtered && error" class="alw-feedback err">告警读取失败：{{ error }} <text class="retry" @click="load()">重试</text></text>

  <AlarmSpeciesPicker />

  <!-- 挂杆 + 挂牌墙 -->
  <view class="alw-rail"/>
  <view class="alw-wall">
    <view v-for="(a, i) in pending" :key="a.id" class="hang">
      <view class="string"/>
      <view class="tag" :class="{ alt: i % 2 === 1 }" @click="host.openAlarm(a)">
        <view class="r1">
          <text class="sp">{{ a.species }}</text>
          <text class="x mono">×{{ a.count }}</text>
          <text class="st">待处理</text>
        </view>
        <text class="meta mono">{{ shortTime(a.at) }} · {{ a.site }} · 录像 {{ a.video_time.toFixed(1) }}s</text>
        <view class="conf"><view class="track"><i :style="{ width: Math.round(a.confidence * 100) + '%' }"/></view><text class="mono cv">{{ Math.round(a.confidence * 100) }}%</text></view>
        <view class="acts" @click.stop>
          <text class="main" @click.stop="host.quickRepel(a.id)">▶ 升旗驱离</text>
          <text @click.stop="host.run(() => host.requestIgnore(a.id))">忽略</text>
        </view>
      </view>
    </view>
    <view v-for="a in processing" :key="'p-' + a.id" class="hang">
      <view class="string"/>
      <view class="tag" :class="{ alt: pending.length % 2 === 0 }" @click="host.openAlarm(a)">
        <view class="r1">
          <text class="sp">{{ a.species }}</text>
          <text class="x mono">×{{ a.count }}</text>
          <text class="st run">执行中</text>
        </view>
        <text class="meta mono">{{ shortTime(a.at) }} · {{ a.site }} · {{ activeOf(a) }}</text>
      </view>
    </view>
    <view v-if="!pending.length && !processing.length && !loading && !error" class="hang">
      <view class="string"/>
      <view class="tag empty"><text class="sp">{{ filtered ? '该鸟种暂无进行中告警' : '无进行中告警' }}</text><text class="meta">历史处置见下方工单</text></view>
    </view>
  </view>

  <!-- 历史处置:撕票工单 -->
  <view class="alw-sec"><text class="b">历史处置</text><text class="s">已处理 / 已忽略</text></view>
  <view v-for="a in history" :key="'h-' + a.id" class="alw-ticket" @click="host.openAlarm(a)">
    <view class="mid">
      <text class="t">{{ a.species }} ×{{ a.count }}</text>
      <text class="m mono">{{ shortTime(a.at) }} · 置信 {{ Math.round(a.confidence * 100) }}%</text>
    </view>
    <text class="st" :class="{ dim: a.status === 'ignored' }">{{ names(a.status) }}</text>
    <text class="chev">›</text>
  </view>
  <text v-if="!history.length && !loading && !error" class="alw-feedback">{{ filtered ? '该鸟种暂无历史处置记录' : '暂无历史处置记录' }}</text>
  <button v-if="filtered && hasMore" class="alw-more" :disabled="loading" @click="load(true)">{{ loading ? '加载中…' : '加载更早的该鸟种告警' }}</button>

</template>

<style scoped>
/* ===== 头部 ===== */
.alw-head{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:14px 16px 8px}
.alw-head>view{display:flex;flex-direction:column;gap:3px}
.eyebrow{font-size:8.5px;letter-spacing:2px;color:var(--ink-400);font-weight:700}
.title{font-size:19px;font-weight:900;letter-spacing:3px;color:var(--ink-900)}
.alw-head .tag{border:2px solid var(--ink-900);background:var(--surface-card);color:var(--ink-900);font-size:9px;font-weight:900;letter-spacing:1px;padding:4px 9px;box-shadow:2px 2px 0 var(--shadow-ink)}
.alw-head .tag.hot{background:#d3212c;border-color:#d3212c;color:#fff}
/* 筛选提示 */
.alw-filter{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:0 16px 8px;padding:8px 10px;border:2px solid var(--ink-900);background:var(--surface-card);box-shadow:3px 3px 0 var(--shadow-ink)}
.alw-filter .ft{font-size:11px;font-weight:900;color:var(--ink-900);min-width:0;overflow-wrap:anywhere}
.alw-filter .fc{font-size:10px;font-weight:900;color:#d3212c;text-decoration:underline;cursor:pointer;flex-shrink:0}
.alw-feedback{display:block;margin:2px 16px;padding:6px 2px;font-size:10px;color:var(--ink-400)}
.alw-feedback.err{color:#d3212c;font-weight:700}
.alw-feedback .retry{text-decoration:underline;cursor:pointer}
/* 挂杆 + 挂牌 */
.alw-rail{margin:8px 14px 0;height:6px;background:var(--ink-900)}
.alw-wall{padding:0 18px;position:relative}
.hang{margin:0 -4px 14px;position:relative}
.hang .string{width:0;height:16px;border-left:2px dashed var(--ink-900);margin:0 auto}
.tag{background:var(--surface-card);border:2px solid var(--ink-900);box-shadow:4px 5px 0 var(--shadow-ink);position:relative;padding:15px 12px 11px;transform:rotate(-.6deg);cursor:pointer}
.tag.alt{transform:rotate(.6deg)}
.tag::before{content:'';position:absolute;left:50%;top:4px;transform:translateX(-50%);width:10px;height:10px;border-radius:50%;background:var(--surface-canvas);border:2px solid var(--ink-900)}
.tag .r1{display:flex;align-items:center;gap:8px;min-width:0}
.tag .sp{font-size:15px;font-weight:900;letter-spacing:1px;color:var(--ink-900);min-width:0;overflow-wrap:anywhere}
.tag .x{font-size:11px;font-weight:700;background:var(--ink-900);color:#f5c400;padding:1px 7px;flex-shrink:0}
.tag .st{margin-left:auto;font-size:10px;font-weight:900;border:2px solid var(--ink-900);padding:2px 8px;transform:rotate(-3deg);background:#d3212c;border-color:#d3212c;color:#fff;flex-shrink:0}
.tag .st.run{background:#f5c400;border-color:var(--ink-900);color:var(--ink-900)}
.tag .meta{display:block;font-size:9px;color:var(--ink-400);margin-top:4px;letter-spacing:.5px;overflow-wrap:anywhere}
.tag .conf{display:flex;align-items:center;gap:6px;margin-top:7px}
.tag .track{flex:1;height:8px;border:2px solid var(--ink-900);background:var(--surface-card)}
.tag .track i{display:block;height:100%;background:#f5c400}
.tag .cv{font-size:9.5px;font-weight:700;color:var(--ink-900)}
.tag .acts{display:flex;gap:8px;margin-top:10px}
.tag .acts text{flex:1;text-align:center;font-size:11px;font-weight:900;border:2px solid var(--ink-900);padding:8px 0;cursor:pointer;background:var(--surface-card);color:var(--ink-900)}
.tag .acts .main{background:var(--ink-900);color:#f5c400}
.tag.empty{cursor:default}
.tag.empty .sp{font-size:13px;color:var(--ink-400)}
/* 历史工单 */
.alw-sec{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:14px 14px 8px}
.alw-sec .b{font-size:12.5px;font-weight:900;letter-spacing:2px;color:var(--ink-900)}
.alw-sec .s{font-size:9px;color:var(--ink-400)}
.alw-ticket{display:flex;align-items:center;gap:9px;border:2px solid var(--ink-900);border-left-style:dashed;background:var(--surface-card);box-shadow:3px 3px 0 var(--shadow-ink);margin:0 14px 8px;padding:9px 11px;cursor:pointer}
.alw-ticket .mid{flex:1;min-width:0}
.alw-ticket .t{display:block;font-size:12px;font-weight:900;color:var(--ink-900)}
.alw-ticket .m{display:block;font-size:8.5px;color:var(--ink-400);margin-top:2px}
.alw-ticket .st{flex-shrink:0;font-size:9px;font-weight:900;border:2px solid var(--ink-900);padding:1px 6px;transform:rotate(-2deg);color:var(--ink-900)}
.alw-ticket .st.dim{border-color:var(--ink-400);color:var(--ink-400)}
.alw-ticket .chev{color:var(--ink-400);font-weight:900}
.alw-more{margin:6px 14px;border:2px solid var(--ink-900);background:var(--surface-card);padding:9px;color:var(--ink-900);font-size:11px;font-weight:800}
</style>
