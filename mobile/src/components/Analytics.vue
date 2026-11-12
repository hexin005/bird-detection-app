<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useOrchard } from '../store'
import { useHost } from './host/hostContext'
import { SPECIES_GUIDE } from '../data/speciesGuide'
import type { Stats } from '../types'

const store = useOrchard()
const host = useHost()
const isB = computed(() => host.theme === 'b1bit')
const isSignal = computed(() => host.theme === 'signal')
const range = ref<'today' | '7d' | '30d'>('7d')
const stats = ref<Stats | null>(null)
const loading = ref(false), error = ref('')
const exportOpen = ref(false)
const exportFormat = ref<'csv' | 'json'>('csv')
const selectedDay = ref(-1)
const selectedHour = ref(-1)
const selectedSlice = ref<string | null>(null)
const hoverSlice = ref<string | null>(null)
const animate = ref(false)
const displayNumbers = ref({ sessions: 0, birds: 0, alarms: 0, rate: 0 })
let animationTimer: ReturnType<typeof setTimeout> | undefined
let numberTimer: ReturnType<typeof setTimeout> | undefined
let numberFrame = 0
function animateNumbers(result: Stats) {
  cancelAnimationFrame(numberFrame)
  clearTimeout(numberTimer)
  const target = {
    sessions: (result.task_trend || []).reduce((sum, n) => sum + n, 0),
    birds: (result.bird_trend || []).reduce((sum, n) => sum + n, 0),
    alarms: Object.values(result.breakdown || {}).reduce((sum, n) => sum + n, 0),
    rate: result.exec?.total ? Math.round(result.exec.completed / result.exec.total * 100) : 0,
  }
  if (typeof window === 'undefined' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    displayNumbers.value = target
    return
  }
  displayNumbers.value = { sessions: 0, birds: 0, alarms: 0, rate: 0 }
  const started = performance.now()
  function step(now: number) {
    const progress = Math.min(1, (now - started) / 700)
    const eased = 1 - (1 - progress) ** 3
    displayNumbers.value = {
      sessions: Math.round(target.sessions * eased), birds: Math.round(target.birds * eased),
      alarms: Math.round(target.alarms * eased), rate: Math.round(target.rate * eased),
    }
    if (progress < 1) numberFrame = requestAnimationFrame(step)
  }
  numberFrame = requestAnimationFrame(step)
  numberTimer = setTimeout(() => { cancelAnimationFrame(numberFrame); displayNumbers.value = target }, 850)
}
const notify = (m: string) => uni.showToast({ title: m, icon: 'none', duration: 2500 })

let loadSequence = 0
async function load() {
  const sequence = ++loadSequence
  loading.value = true; error.value = ''
  try {
    const result = await store.request<Stats>('/stats?range=' + range.value)
    if (sequence !== loadSequence) return
    stats.value = result
    animateNumbers(result)
    selectedDay.value = -1
    selectedHour.value = -1
    selectedSlice.value = null
    animate.value = false
    clearTimeout(animationTimer)
    animationTimer = setTimeout(() => { animate.value = true }, 30)
  } catch (e) {
    if (sequence === loadSequence) error.value = (e as Error).message
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}
onBeforeUnmount(() => { ++loadSequence; clearTimeout(animationTimer); clearTimeout(numberTimer); cancelAnimationFrame(numberFrame) })
// 页面常驻 DOM,启动时未登录:仅在切入本页时加载
defineExpose({ load })
function pick(next: 'today' | '7d' | '30d') { if (range.value !== next) { range.value = next; void load() } }

const counts = computed(() => ({
  events: stats.value?.breakdown ? stats.value.breakdown.new + stats.value.breakdown.processing + stats.value.breakdown.handled + stats.value.breakdown.ignored : 0,
  alarms: stats.value?.exec ? stats.value.exec.total : 0,
  exec: stats.value?.exec?.completed ?? 0,
}))
const buckets = computed(() => stats.value?.range_days ?? 7)
/** 兼容旧版 /stats:缺 dates 时按 range_days 倒推自然日 */
function safeDates(data: Stats | null): string[] {
  if (!data) return []
  if (data.dates?.length) return data.dates
  const n = data.range_days || (data.trend?.length ?? 1)
  const out: string[] = []
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000)
    out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)
  }
  return out
}
const daily = computed(() => {
  const data = stats.value
  if (!data) return []
  const taskTrend = data.task_trend || []
  const birdTrend = data.bird_trend || []
  const maxSessions = Math.max(1, ...taskTrend)
  const maxBirds = Math.max(1, ...birdTrend)
  return safeDates(data).map((date, index) => ({
    date, sessions: taskTrend[index] || 0, birds: birdTrend[index] || 0,
    alarms: data.trend?.[index] || 0,
    sessionHeight: taskTrend[index] ? Math.max(6, Math.round(taskTrend[index] / maxSessions * 100)) : 0,
    birdHeight: birdTrend[index] ? Math.max(6, Math.round(birdTrend[index] / maxBirds * 100)) : 0,
  }))
})
const birdBars = computed(() => {
  const data = stats.value?.bird_species ?? []
  const max = Math.max(1, ...data.map(item => item.count))
  return data.map(item => ({ ...item, pct: Math.round(item.count / max * 100) }))
})
const chartDetail = computed(() => {
  const day = daily.value[selectedDay.value]
  return day ? `${day.date} · ${day.sessions} 场检测 · ${day.birds} 只鸟 · ${day.alarms} 条告警` : ''
})
const hourDetail = computed(() => selectedHour.value >= 0 ? `${String(selectedHour.value).padStart(2, '0')}:00—${String(selectedHour.value).padStart(2, '0')}:59 · ${stats.value?.hourly[selectedHour.value] || 0} 条告警` : peakHours.value)
const rangeLabel = computed(() => ({ today: '今日', '7d': '近 7 天', '30d': '近 30 天' })[range.value])
const rangeDates = computed(() => { const ds = safeDates(stats.value); return ds.length ? `${ds[0]} ~ ${ds[ds.length - 1]}` : '' })
function openGuide(species: string) {
  if (SPECIES_GUIDE.some(item => item.name === species)) host.viewSpeciesGuide(species)
}
function csvCell(value: string | number | null) {
  const text = String(value ?? '')
  return `"${text.replace(/"/g, '""')}"`
}
function exportData() {
  if (!stats.value || typeof document === 'undefined') { notify('暂无可导出的数据'); return }
  const data = stats.value
  const filename = `orchard-stats-${range.value}-${data.dates?.[data.dates.length - 1]?.replace(/-/g, '') || 'today'}`
  let content: string, mime: string
  if (exportFormat.value === 'json') {
    content = JSON.stringify({ range: range.value, ...data }, null, 2)
    mime = 'application/json;charset=utf-8'
  } else {
    const taskTrend = data.task_trend || [], birdTrend = data.bird_trend || []
    const rows: (string | number | null)[][] = [
      ['日期', '检测场次', '发现鸟数', '检测告警数'],
      ...safeDates(data).map((date, i) => [date, taskTrend[i] || 0, birdTrend[i] || 0, data.trend?.[i] || 0]),
      [], ['鸟种分布', '发现鸟数'], ...(data.bird_species || []).map(item => [item.species, item.count]),
      [], ['时段', '告警数'], ...(data.hourly || []).map((count, hour) => [String(hour).padStart(2, '0') + ':00', count]),
      [], ['告警状态', '数量'], ...Object.entries(data.breakdown || {}),
      [], ['驱离执行', '数值'], ...Object.entries(data.exec || {}),
    ]
    content = '\uFEFF' + rows.map(row => row.map(csvCell).join(',')).join('\r\n')
    mime = 'text/csv;charset=utf-8'
  }
  const url = URL.createObjectURL(new Blob([content], { type: mime }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename + '.' + exportFormat.value
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  exportOpen.value = false
}
/** 折线:SVG viewBox 336x108,点均分,高度按最大值比例 */
const line = computed(() => {
  const data = stats.value?.trend ?? []
  const max = Math.max(1, ...data)
  const inner = { x: 24, y: 92, w: 276 }
  const step = data.length > 1 ? inner.w / (data.length - 1) : 0
  const points = data.map((v, i) => ({ x: inner.x + i * step, y: inner.y - (v / max) * 78, v }))
  return { points, poly: points.map(p => `${p.x},${p.y}`).join(' '), max }
})
const bars = computed(() => {
  const data = stats.value?.species ?? []
  const max = Math.max(1, ...data.map(d => d.count))
  return data.map((d, i) => ({ ...d, pct: Math.round(d.count / max * 100), dim: i >= 2 }))
})
const heatLevel = (v: number): string => v === 0 ? 'l0' : v <= 1 ? 'l1' : v <= 3 ? 'l2' : 'l3'
const peakHours = computed(() => {
  const h = stats.value?.hourly ?? []
  const max = Math.max(...h)
  if (!max) return '暂无活动数据 — 开始监测后按小时聚合'
  const peaks = h.map((v, i) => ({ v, i })).filter(x => x.v === max).map(x => x.i)
  return `峰值 ${peaks.map(i => `${String(i).padStart(2, '0')} 时`).join(' / ')} — 建议在该时段前后保持双模待机`
})
const fmtSeconds = (v: number | null | undefined) => v == null ? '暂无' : `${v.toFixed(1)}s`
const pctText = (share: number | null | undefined) => share == null ? '暂无' : `${Math.round(share * 100)}%`
const segWidths = computed(() => {
  const b = stats.value?.breakdown
  if (!b) return { handled: 0, ignored: 0, other: 0 }
  const total = b.new + b.processing + b.handled + b.ignored
  if (!total) return { handled: 0, ignored: 0, other: 0 }
  return {
    handled: Math.round(b.handled / total * 100),
    ignored: Math.round(b.ignored / total * 100),
    other: 100 - Math.round(b.handled / total * 100) - Math.round(b.ignored / total * 100),
  }
})
const dateLabels = computed(() => {
  const n = buckets.value
  if (n === 1) return ['今日']
  const labels: string[] = []
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000)
    labels.push(`${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)
  }
  return labels
})

/* ================= C 统计板(告警条数口径) ================= */
const alarmTotal = computed(() => stats.value ? Object.values(stats.value.breakdown || {}).reduce((sum, value) => sum + value, 0) : 0)
/** 折线数据:峰值=最大值日,红色方块标记 */
const linePts = computed(() => {
  const data = stats.value
  if (!data) return []
  const values = data.trend || []
  const dates = safeDates(data)
  const max = Math.max(1, ...values)
  const step = values.length > 1 ? 324 / (values.length - 1) : 0
  const peaks = new Set(values.map((v, i) => ({ v, i })).filter(x => x.v === max && x.v > 0).map(x => x.i))
  return values.map((v, i) => ({ i, v, date: dates[i] || '', x: Math.round(6 + i * step), y: Math.round(100 - (v / max) * 88), peak: peaks.has(i) }))
})
const linePoly = computed(() => linePts.value.map(p => `${p.x},${p.y}`).join(' '))
const lineArea = computed(() => linePts.value.length ? linePoly.value + ` ${linePts.value[linePts.value.length - 1].x},100 6,100` : '')
const lineLabels = computed(() => {
  const ds = safeDates(stats.value)
  if (!ds.length) return []
  if (ds.length <= 7) return ds.map(d => range.value === 'today' ? '今日' : d.slice(5))
  return ds.map((d, i) => (i % 5 === 0 || i === ds.length - 1) ? d.slice(5) : '')
})
const lineCap = computed(() => {
  if (selectedDay.value >= 0) {
    const p = linePts.value[selectedDay.value]
    return p ? `${p.date} · ${p.v} 条告警` : ''
  }
  const peaks = linePts.value.filter(p => p.peak)
  return peaks.length ? `峰值 ${peaks.map(p => `${p.date.slice(5)} · ${p.v} 条`).join(' / ')}（红色方块）· 点选方块查看当日` : '本范围暂无峰值 · 点选方块查看当日条数'
})
/** 物种排行:头名警示纹,高危标红点 */
const rankRows = computed(() => {
  const data = stats.value?.species ?? []
  const max = Math.max(1, ...data.map(d => d.count))
  return data.map((d, i) => ({ ...d, pct: Math.round(d.count / max * 100), hz: i === 0, guide: SPECIES_GUIDE.some(s => s.name === d.species) }))
})
/** 饼图:已处理=墨黑/已忽略=灰/执行中=黄/待处理=红,pathLength=100 扇区 */
const pieSlices = computed(() => {
  const b = stats.value?.breakdown
  if (!b) return []
  const rows = [
    { label: '已处理', v: b.handled, color: '#191919' },
    { label: '已忽略', v: b.ignored, color: '#cfcdbc' },
    { label: '执行中', v: b.processing, color: '#f5c400' },
    { label: '待处理', v: b.new, color: '#d3212c' },
  ].filter(r => r.v > 0)
  const total = rows.reduce((sum, r) => sum + r.v, 0)
  let cum = 0
  return rows.map(r => {
    const pct = r.v / total * 100
    const seg = { ...r, pct: Math.round(pct), dash: pct, offset: -cum }
    cum += pct
    return seg
  })
})
const activeSlice = computed(() => hoverSlice.value || selectedSlice.value)
const pieCap = computed(() => {
  const label = activeSlice.value
  if (label) {
    const row = pieSlices.value.find(r => r.label === label)
    return row ? `${row.label} · ${row.v} 条 · 占 ${row.pct}%${selectedSlice.value === label ? '（再次点选取消）' : ''}` : ''
  }
  return '悬停或点选扇区:该扇区加粗放大、其余淡出'
})
function toggleSlice(label: string) { selectedSlice.value = selectedSlice.value === label ? null : label }
function onPieBg() { selectedSlice.value = null }
</script>

<template>
  <view class="qh-header">
    <view class="qh-header__brand">
      <text class="qh-page-title">果园数据分析</text>
      <text class="qh-page-subtitle">{{ isSignal ? '东区观察手册 · 按自然日统计告警' : '统计覆盖整个演示果园 · 自然日口径' }}</text>
    </view>
    <button v-if="isB || isSignal" class="qh-an-export" :class="{ 'is-signal': isSignal }" :disabled="!stats || loading" @click="exportOpen = true">↓ 导出</button>
  </view>

  <template v-if="isB">
    <view class="qh-an-hero" :class="{ 'is-animated': animate }">
      <view><b>{{ displayNumbers.sessions }}</b><text>检测场次</text></view>
      <view><b>{{ displayNumbers.birds }}</b><text>发现鸟数</text></view>
      <view><b>{{ displayNumbers.alarms }}</b><text>检测告警</text></view>
      <view><b>{{ displayNumbers.rate }}%</b><text>驱离完成率</text></view>
    </view>
    <view class="qh-an-chips">
      <button :class="{ on: range === 'today' }" @click="pick('today')">今日</button>
      <button :class="{ on: range === '7d' }" @click="pick('7d')">近 7 天</button>
      <button :class="{ on: range === '30d' }" @click="pick('30d')">近 30 天</button>
    </view>
    <view class="qh-window">
      <view class="qh-tbar"><view class="qh-tbar__box">×</view><text class="qh-tbar__t">检测趋势 · {{ rangeLabel }}（场次 × 鸟数）</text></view>
      <view class="qh-window__bd">
        <view class="qh-an-chartlegend"><text><i />检测场次</text><text><i />发现鸟数</text></view>
        <view class="qh-an-chart" :class="{ 'is-animated': animate, 'is-month': buckets === 30 }">
          <button v-for="(day, i) in daily" :key="day.date" class="qh-an-day" :class="{ 'is-selected': selectedDay === i }" :aria-label="chartDetail && selectedDay === i ? chartDetail : `${day.date} ${day.sessions} 场 ${day.birds} 只`" @click="selectedDay = selectedDay === i ? -1 : i">
            <i class="qh-an-column" :style="{ height: day.sessionHeight + '%', animationDelay: (i * 28) + 'ms' }" />
            <i class="qh-an-column qh-an-column--birds" :style="{ height: day.birdHeight + '%', animationDelay: (i * 28 + 50) + 'ms' }" />
          </button>
        </view>
        <view class="qh-an-dates"><text v-for="(day, i) in daily" :key="day.date" v-show="buckets !== 30 || i % 5 === 0 || i === 29">{{ buckets === 1 ? '今日' : day.date.slice(5) }}</text></view>
        <text class="qh-an-sub">{{ chartDetail || '点按柱体查看当日场次、鸟数与告警' }} · 每场按物种峰值计数</text>
      </view>
    </view>
    <view class="qh-window">
      <view class="qh-tbar"><view class="qh-tbar__box">×</view><text class="qh-tbar__t">鸟种分布 · TOP 5（按发现鸟数）</text></view>
      <view class="qh-window__bd">
        <view v-if="birdBars.length" class="qh-an-bars qh-an-birdbars" :class="{ 'is-animated': animate }">
          <view v-for="(item, i) in birdBars" :key="item.species" class="qh-an-bar">
            <button class="nm" :disabled="!SPECIES_GUIDE.some(s => s.name === item.species)" @click="openGuide(item.species)">{{ item.species }} ›</button>
            <view class="tr"><view class="fl" :class="{ d: i > 1 }" :style="{ width: item.pct + '%', animationDelay: (i * 90) + 'ms' }" /></view>
            <text class="v">{{ item.count }}</text>
          </view>
        </view>
        <text v-else class="qh-an-sub">范围内暂无已归档视频的鸟类记录</text>
        <text class="qh-an-sub">每场每物种只取峰值 · 点物种名称查看知识卡</text>
      </view>
    </view>
    <view class="qh-window">
      <view class="qh-tbar"><view class="qh-tbar__box">×</view><text class="qh-tbar__t">时段活动 · 24H（告警）</text></view>
      <view class="qh-window__bd">
        <view class="qh-an-hourchart" :class="{ 'is-animated': animate }">
          <button v-for="(value, hour) in (stats?.hourly ?? [])" :key="hour" :class="{ 'is-peak': value > 0 && value === Math.max(...(stats?.hourly ?? [])), 'is-selected': selectedHour === hour }" :style="{ height: Math.max(4, value / Math.max(1, ...(stats?.hourly ?? [])) * 100) + '%', animationDelay: (hour * 22) + 'ms' }" :aria-label="`${hour} 时 ${value} 条告警`" @click="selectedHour = selectedHour === hour ? -1 : hour" />
        </view>
        <view class="qh-an-heat-x"><text>0</text><text>6</text><text>12</text><text>18</text><text>23</text></view>
        <text class="qh-an-peak">{{ hourDetail }}</text>
      </view>
    </view>
  </template>

  <template v-else-if="isSignal">
    <view class="sgb">
      <view class="sgb-head">
        <view class="hl"><text class="ttl">鸟情统计板</text><text class="tag">STATS BOARD</text></view>
        <view class="vol"><text>按告警条数统计</text><text>不累计鸟只数</text></view>
      </view>
      <view class="sgb-ranges">
        <text :class="{ on: range === 'today' }" @click="pick('today')">今日</text>
        <text :class="{ on: range === '7d' }" @click="pick('7d')">近 7 天</text>
        <text :class="{ on: range === '30d' }" @click="pick('30d')">近 30 天</text>
      </view>

      <view v-if="loading" class="sgb-note">正在读取 {{ rangeLabel }} 的统计数据…</view>
      <view v-else-if="error" class="sgb-note err">统计读取失败：{{ error }} <text class="retry" @click="load">重试</text></view>
      <template v-else-if="stats">
        <!-- 翻牌数板 -->
        <view class="sgb-flips">
          <view class="flip"><b class="mono">{{ alarmTotal }}</b><span>检测告警 · 条</span></view>
          <view class="flip"><b class="mono">{{ stats.exec?.total ?? 0 }}</b><span>驱离执行 · 次</span></view>
          <view class="flip"><b class="mono">{{ stats.exec?.total ? Math.round(stats.exec.completed / stats.exec.total * 100) + '%' : '—' }}</b><span>执行完成率</span></view>
          <view class="flip"><b class="mono">{{ fmtSeconds(stats.exec?.avg_start_seconds) }}</b><span>平均启动响应</span></view>
        </view>

        <!-- 每日告警 · 折线 -->
        <view class="sgb-win">
          <view class="tbar"><i class="sq"/><text class="t">每日告警 · 折线</text><text class="sub">{{ rangeLabel }}{{ rangeDates ? ' · ' + rangeDates : '' }} · 条</text></view>
          <view class="bd">
            <view v-if="alarmTotal" class="linewrap">
              <svg viewBox="0 0 336 110" width="336" height="110">
                <line x1="6" y1="12" x2="330" y2="12" class="grid"/>
                <line x1="6" y1="56" x2="330" y2="56" class="grid"/>
                <polygon v-if="linePts.length" :points="lineArea" class="area"/>
                <polyline :points="linePoly" class="ln"/>
                <g fill="#191919">
                  <rect v-for="p in linePts.filter(p => !p.peak)" :key="'m' + p.i" class="mk" :x="p.x - 2" :y="p.y - 2" width="4" height="4" @click="selectedDay = selectedDay === p.i ? -1 : p.i">
                    <title>{{ p.date }} · {{ p.v }} 条</title>
                  </rect>
                </g>
                <g fill="#d3212c">
                  <rect v-for="p in linePts.filter(p => p.peak)" :key="'p' + p.i" class="mk hot" :x="p.x - 3.5" :y="p.y - 3.5" width="7" height="7" stroke="#191919" stroke-width="1.5" @click="selectedDay = selectedDay === p.i ? -1 : p.i">
                    <title>{{ p.date }} · {{ p.v }} 条</title>
                  </rect>
                </g>
              </svg>
              <view class="dates"><text v-for="(l, i) in lineLabels" :key="i">{{ l }}</text></view>
              <text class="cap">{{ lineCap }}</text>
            </view>
            <text v-else class="cap empty">本范围无告警；归档视频的检测记录可在「记录」页查看。</text>
          </view>
        </view>

        <!-- 告警物种 · 条形排行 -->
        <view class="sgb-win">
          <view class="tbar"><i class="sq"/><text class="t">告警物种 · TOP5 条形</text><text class="sub">条数 · 高危标红</text></view>
          <view class="bd">
            <view v-if="rankRows.length" class="rank">
              <view v-for="r in rankRows" :key="r.species" class="row" @click="r.guide && openGuide(r.species)">
                <text class="nm"><text v-if="r.guide" class="dot">●</text> {{ r.species }}</text>
                <view class="track"><i :class="{ hz: r.hz }" :style="{ width: r.pct + '%' }"/></view>
                <text class="v mono">{{ r.count }}</text>
              </view>
            </view>
            <text v-else class="cap empty">本范围没有告警物种记录。</text>
            <text v-if="rankRows.length" class="cap">点物种名可跳转知识卡 · 头名挂警示纹</text>
          </view>
        </view>

        <!-- 告警状态构成 · 饼图 -->
        <view class="sgb-win">
          <view class="tbar"><i class="sq"/><text class="t">告警状态构成 · 饼图</text><text class="sub">{{ alarmTotal }} 条</text></view>
          <view class="bd">
            <view v-if="alarmTotal" class="piewrap" :class="{ focus: !!activeSlice }" @click="onPieBg">
              <svg class="pie" viewBox="0 0 140 140" width="140" height="140">
                <g v-for="s in pieSlices" :key="s.label" class="slice" :class="{ cur: activeSlice === s.label }" @click.stop="toggleSlice(s.label)" @mouseenter="hoverSlice = s.label" @mouseleave="hoverSlice = null">
                  <circle class="ink" cx="70" cy="70" r="40" fill="none" stroke="#191919" stroke-width="30" pathLength="100" :stroke-dasharray="`${s.dash} ${100 - s.dash}`" :stroke-dashoffset="s.offset" transform="rotate(-90 70 70)" pointer-events="none"/>
                  <circle class="fill" cx="70" cy="70" r="40" fill="none" :stroke="s.color" stroke-width="26" pathLength="100" :stroke-dasharray="`${s.dash} ${100 - s.dash}`" :stroke-dashoffset="s.offset" transform="rotate(-90 70 70)"/>
                </g>
                <text x="70" y="67" text-anchor="middle" font-size="19" font-weight="900" font-family="Consolas,monospace" fill="#191919" pointer-events="none">{{ alarmTotal }}</text>
                <text x="70" y="81" text-anchor="middle" font-size="8" letter-spacing="2" fill="#6f6f68" pointer-events="none">总条数</text>
              </svg>
              <view class="plegend">
                <view v-for="s in pieSlices" :key="s.label" class="r" @click.stop="toggleSlice(s.label)"><i :style="{ background: s.color }"/><text>{{ s.label }}</text><b class="mono">{{ s.v }} · {{ s.pct }}%</b></view>
              </view>
            </view>
            <text v-else class="cap empty">本范围没有告警，暂无状态构成。</text>
            <text v-if="alarmTotal" class="cap">{{ pieCap }}</text>
          </view>
        </view>

        <!-- 时段活动 · 24H -->
        <view class="sgb-win">
          <view class="tbar"><i class="sq"/><text class="t">时段活动 · 24H</text><text class="sub">告警条数</text></view>
          <view class="bd">
            <view v-if="alarmTotal" class="heat">
              <i v-for="(v, h) in (stats.hourly || [])" :key="h" :class="[heatLevel(v), { picked: selectedHour === h }]" :title="`${h} 时 · ${v} 条`" @click="selectedHour = selectedHour === h ? -1 : h"/>
            </view>
            <view v-if="alarmTotal" class="heatx"><text>0</text><text>6</text><text>12</text><text>18</text><text>23</text></view>
            <text class="cap" :class="{ empty: !alarmTotal }">{{ alarmTotal ? hourDetail : '本范围暂无时段告警数据' }}</text>
          </view>
        </view>

        <!-- 驱离执行 · 读数 -->
        <view class="sgb-win">
          <view class="tbar"><i class="sq"/><text class="t">驱离执行 · 读数</text><text class="sub">模拟执行器</text></view>
          <view class="bd">
            <view class="gauge">
              <view class="num"><b class="mono">{{ stats.exec?.total ? Math.round(stats.exec.completed / stats.exec.total * 100) + '%' : '—' }}</b><span>完成率</span></view>
              <view class="mini">
                <view class="r"><text>执行 {{ stats.exec?.total ?? 0 }} 次</text><b class="mono">完成 {{ stats.exec?.completed ?? 0 }} · 失败 {{ stats.exec?.failed ?? 0 }}</b></view>
                <view class="r"><text>双模占比</text><b class="mono">{{ pctText(stats.exec?.dual_share) }}</b></view>
                <view class="r last"><text>平均完成耗时</text><b class="mono">{{ fmtSeconds(stats.exec?.avg_done_seconds) }}</b></view>
              </view>
            </view>
            <text class="cap">没有执行时，读数仅展示原始统计，不推断驱离效果。</text>
          </view>
        </view>
      </template>
    </view>
  </template>

  <template v-else>
  <!-- 总览 + 时间范围 -->
  <view class="qh-card">
    <view class="qh-an-range">
      <text :class="{ on: range === 'today' }" @click="pick('today')">今日</text>
      <text :class="{ on: range === '7d' }" @click="pick('7d')">近 7 天</text>
      <text :class="{ on: range === '30d' }" @click="pick('30d')">近 30 天</text>
    </view>
    <view class="qh-an-bignums">
      <view><b>{{ counts.events }}</b><span>检测告警</span></view>
      <view><b>{{ stats?.exec.total ?? 0 }}</b><span>驱离执行</span></view>
      <view><b>{{ pctText(stats?.exec ? (stats.exec.completed / Math.max(1, stats.exec.total)) : null) }}</b><span>完成率</span></view>
    </view>
  </view>

  <!-- 检测趋势 -->
  <view class="qh-window">
    <view class="qh-tbar"><view class="qh-tbar__box">×</view><text class="qh-tbar__t">检测趋势 · 近 {{ buckets }} 天</text></view>
    <view class="qh-window__bd">
      <view class="qh-an-line">
        <view class="grid" style="top:0"></view><view class="grid" style="top:33%"></view><view class="grid" style="top:66%"></view>
        <svg width="336" height="108" viewBox="0 0 336 108">
          <polyline :points="line.poly" fill="none" stroke="currentColor" stroke-width="2.5" style="color:var(--ink-900)" />
          <g>
            <rect v-for="(p, i) in line.points" :key="i" :x="p.x - 3" :y="p.y - 3" width="6" height="6" style="fill:var(--ink-900)" />
          </g>
        </svg>
      </view>
      <view class="qh-an-xlab"><text v-for="(label, i) in dateLabels" :key="i">{{ label }}</text></view>
      <text class="qh-an-sub">口径:按自然日聚合的检测告警事件数(非逐帧识别次数)</text>
    </view>
  </view>

  <!-- 鸟种分布 -->
  <view class="qh-window">
    <view class="qh-tbar"><view class="qh-tbar__box">×</view><text class="qh-tbar__t">鸟种分布 · TOP 5</text></view>
    <view class="qh-window__bd">
      <view v-if="bars.length" class="qh-an-bars">
        <view v-for="b in bars" :key="b.species" class="qh-an-bar">
          <text class="nm">{{ b.species }}</text>
          <view class="tr"><view class="fl" :class="{ d: b.dim }" :style="{ width: b.pct + '%' }" /></view>
          <text class="v">{{ b.count }}</text>
        </view>
      </view>
      <text v-else class="qh-note" style="display:block;padding:16px 0">范围内暂无告警 — 开始监测后自动生成</text>
      <text v-if="bars.length" class="qh-an-sub">按告警条数统计,不累计鸟只数</text>
    </view>
  </view>

  <!-- 24H 时段活动 -->
  <view class="qh-window">
    <view class="qh-tbar"><view class="qh-tbar__box">×</view><text class="qh-tbar__t">时段活动 · 24H</text></view>
    <view class="qh-window__bd">
      <view class="qh-an-heat">
        <i v-for="(v, i) in (stats?.hourly ?? [])" :key="i" :class="heatLevel(v)" />
      </view>
      <view class="qh-an-heat-x"><text>0</text><text>6</text><text>12</text><text>18</text><text>23</text></view>
      <text class="qh-an-peak">{{ peakHours }}</text>
    </view>
  </view>

  </template>

  <template v-if="!isSignal">
  <!-- 告警处理构成 -->
  <view class="qh-window">
    <view class="qh-tbar"><view class="qh-tbar__box">×</view><text class="qh-tbar__t">告警处理构成</text></view>
    <view class="qh-window__bd">
      <view class="qh-an-seg">
        <view class="s1" :style="{ width: segWidths.handled + '%' }" />
        <view class="s2" :style="{ width: segWidths.ignored + '%' }" />
        <view class="s3" :style="{ width: segWidths.other + '%' }" />
      </view>
      <view class="qh-an-legend">
        <span><i style="background:var(--ink-900)" />已处理 {{ stats?.breakdown.handled ?? 0 }}</span>
        <span><i />已忽略 {{ stats?.breakdown.ignored ?? 0 }}</span>
        <span><i style="background:var(--surface-card)" />待处理 {{ stats?.breakdown.new ?? 0 }}</span>
      </view>
      <text class="qh-an-sub">执行中 {{ stats?.breakdown.processing ?? 0 }} 条 · 状态覆盖待处理/执行中/已处理/已忽略</text>
    </view>
  </view>

  <!-- 驱离执行 -->
  <view class="qh-window">
    <view class="qh-tbar"><view class="qh-tbar__box">×</view><text class="qh-tbar__t">驱离执行 · 模拟执行器</text></view>
    <view class="qh-window__bd">
      <view class="qh-an-bignums" :class="{ 'qh-an-bignums--four': isB }" style="margin-top:0">
        <view><b>{{ stats?.exec.total ?? 0 }}</b><span>执行次数</span></view>
        <view><b>{{ stats?.exec.completed ?? 0 }}</b><span>完成</span></view>
        <view><b>{{ fmtSeconds(stats?.exec.avg_start_seconds) }}</b><span>平均启动响应</span></view>
        <view v-if="isB"><b>{{ pctText(stats?.exec.dual_share) }}</b><span>双模占比</span></view>
      </view>
      <view class="qh-an-rate">
        <i :style="{ width: (stats?.exec.total ? Math.round((stats.exec.completed / stats.exec.total) * 100) : 0) + '%' }" />
        <b>完成率 {{ stats?.exec.total ? Math.round((stats.exec.completed / stats.exec.total) * 100) : 0 }}%</b>
      </view>
      <text class="qh-an-sub">平均完成耗时 <b>{{ fmtSeconds(stats?.exec.avg_done_seconds) }}</b> · 双模联动占 <b>{{ pctText(stats?.exec.dual_share) }}</b>(分母=已完成指令)· 失败 {{ stats?.exec.failed ?? 0 }} 次</text>
    </view>
  </view>
  </template>

  <text v-if="error && !isSignal" class="qh-note" style="display:block">{{ error }}</text>
  <text v-if="loading && !isSignal" class="qh-note">加载中…</text>
  <text class="qh-note">图表随主题联动换肤 · 数据来自果园服务实时统计</text>

  <view v-if="(isB || isSignal) && exportOpen" class="qh-mask qh-mask--bottom is-open" @click.self="exportOpen = false">
    <view class="qh-sheet qh-an-sheet">
      <view class="qh-sheet__grab" />
      <view class="qh-sheet__titlerow"><text class="qh-sheet__title">导出统计数据</text><button class="qh-iconbtn--sm" aria-label="关闭导出弹层" @click="exportOpen = false">×</button></view>
      <text class="qh-an-sheetlabel">范围 · 跟随当前页面</text>
      <view class="qh-an-exportoption is-on">{{ rangeLabel }} <text>{{ rangeDates }}</text></view>
      <text class="qh-an-sheetlabel">格式</text>
      <button class="qh-an-exportoption" :class="{ 'is-on': exportFormat === 'csv' }" @click="exportFormat = 'csv'">CSV · Excel 可直接打开 <text>UTF-8 BOM</text></button>
      <button class="qh-an-exportoption" :class="{ 'is-on': exportFormat === 'json' }" @click="exportFormat = 'json'">JSON · 原始数据 <text>二次分析</text></button>
      <text class="qh-an-sheetlabel">包含内容</text>
      <text class="qh-an-sub">逐日场次 / 鸟数 / 告警 · 物种排行 · 24H 时段 · 告警构成 · 驱离执行</text>
      <button class="qh-btn qh-btn--primary qh-an-exportsubmit" @click="exportData">↓ 导出 {{ exportFormat.toUpperCase() }}</button>
      <text class="qh-an-sub">文件在当前浏览器生成，所选范围的数据不会上传到其它服务</text>
    </view>
  </view>
</template>

<style scoped>
/* 导出入口:B 走 1-bit 硬边; C 用信号黄底,与统计板色标一致 */
.qh-an-export.is-signal{background:#f5c400;font-weight:900;letter-spacing:1px}
.qh-an-export.is-signal:active{transform:translate(1px,1px);box-shadow:1px 1px 0 var(--shadow-ink)}
/* ============ C 鸟情统计板 ============ */
.sgb{display:flex;flex-direction:column;color:var(--ink-900)}
.sgb-head{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:14px 16px 10px}
.sgb-head .hl{display:flex;align-items:center;gap:8px}
.sgb-head .ttl{font-size:19px;font-weight:900;letter-spacing:3px}
.sgb-head .tag{background:#f5c400;border:2px solid var(--ink-900);color:var(--ink-900);font-size:9px;font-weight:900;letter-spacing:2px;padding:3px 8px;box-shadow:2px 2px 0 var(--shadow-ink)}
.sgb-head .vol{display:flex;flex-direction:column;align-items:flex-end;gap:2px}
.sgb-head .vol text{font-size:9px;color:var(--ink-400);letter-spacing:1px}
.sgb-ranges{display:flex;gap:8px;margin:0 14px 12px}
.sgb-ranges text{flex:1;text-align:center;border:2px solid var(--ink-900);background:var(--surface-card);font-size:11px;font-weight:800;padding:7px 0;box-shadow:2px 2px 0 var(--shadow-ink);cursor:pointer}
.sgb-ranges text.on{background:var(--ink-900);color:#f5c400}
.sgb-note{margin:4px 14px;border:2px solid var(--ink-900);background:var(--surface-card);padding:10px 12px;font-size:11px;color:var(--ink-700)}
.sgb-note.err{color:#d3212c;font-weight:700}
.sgb-note .retry{text-decoration:underline;cursor:pointer}
/* 翻牌数板 */
.sgb-flips{display:flex;flex-wrap:wrap;gap:8px;margin:0 14px}
.sgb-flips .flip{width:calc(50% - 4px);background:var(--ink-900);color:#f5c400;padding:10px 0 8px;text-align:center;position:relative}
.sgb-flips .flip::before{content:'';position:absolute;inset:3px;border:1px solid rgba(245,196,0,.45);pointer-events:none}
.sgb-flips .flip b{font-size:26px;font-weight:700;line-height:1.1}
.sgb-flips .flip b.small{font-size:12px}
.sgb-flips .flip span{display:block;font-size:8.5px;letter-spacing:2px;color:#9a9a92;margin-top:3px;font-weight:700}
/* 图表窗口 */
.sgb-win{border:2px solid var(--ink-900);background:var(--surface-card);box-shadow:3px 4px 0 var(--shadow-ink);margin:12px 14px 0}
.sgb-win .tbar{height:22px;background:var(--surface-card);border-bottom:2px solid var(--ink-900);display:flex;align-items:center;gap:6px;padding:0 8px}
.sgb-win .tbar .sq{width:10px;height:10px;border:2px solid var(--ink-900);background:#f5c400;flex-shrink:0}
.sgb-win .tbar .t{font-size:10px;font-weight:900;letter-spacing:1px;background:var(--ink-900);color:#f5c400;padding:1px 8px;white-space:nowrap}
.sgb-win .tbar .sub{margin-left:auto;font-size:8px;color:var(--ink-400);letter-spacing:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sgb-win .bd{padding:10px}
.sgb-win .cap{font-size:9px;color:var(--ink-400);margin-top:6px;line-height:1.5}
.sgb-win .cap.empty{color:var(--ink-400);padding:14px 2px 8px}
/* 折线 */
.linewrap svg{display:block;width:100%;height:auto}
.linewrap .grid{stroke:#c8c6ba;stroke-width:1;stroke-dasharray:3 3}
.linewrap .area{fill:rgba(245,196,0,.18)}
.linewrap .ln{fill:none;stroke:var(--ink-900);stroke-width:2.5}
.linewrap .mk{cursor:pointer;transition:transform .12s;transform-box:fill-box;transform-origin:center}
.linewrap .mk:hover{transform:scale(1.8)}
.linewrap .mk.hot:hover{transform:scale(1.35)}
.linewrap .dates{display:flex;justify-content:space-between;font-size:7.5px;color:var(--ink-400);margin-top:3px;font-weight:700;min-height:10px}
/* 物种排行 */
.rank{display:flex;flex-direction:column;gap:8px}
.rank .row{display:flex;align-items:center;gap:8px;padding:3px 4px;margin:-3px -4px;transition:background .12s}
.rank .row:hover{background:var(--surface-sunken);outline:2px solid var(--ink-900);outline-offset:-2px}
.rank .nm{width:78px;font-size:11px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--ink-900)}
.rank .nm .dot{color:#d3212c;font-size:9px}
.rank .track{flex:1;height:13px;border:2px solid var(--ink-900);background:var(--surface-card)}
.rank .track i{display:block;height:100%;background:var(--ink-900);transition:background .12s}
.rank .row:hover .track i{background:#f5c400}
.rank .track i.hz{background:repeating-linear-gradient(-45deg,#f5c400 0 8px,var(--ink-900) 8px 16px)}
.rank .row:hover .track i.hz{background:repeating-linear-gradient(-45deg,#d3212c 0 8px,var(--ink-900) 8px 16px)}
.rank .v{width:34px;text-align:right;font-size:11px;color:var(--ink-900)}
/* 饼图 */
.piewrap{display:flex;align-items:center;gap:12px}
.pie{flex-shrink:0}
.pie .slice{cursor:pointer;transition:opacity .16s ease}
.pie .slice circle{transition:stroke-width .14s steps(3)}
.piewrap.focus .slice{opacity:.22}
.piewrap.focus .slice.cur{opacity:1}
.piewrap.focus .slice.cur .ink{stroke-width:37}
.piewrap.focus .slice.cur .fill{stroke-width:33}
.plegend{flex:1;display:flex;flex-direction:column;gap:6px;min-width:0}
.plegend .r{display:flex;align-items:center;gap:6px;font-size:10px;font-weight:700;color:var(--ink-900);cursor:pointer}
.plegend .r i{width:10px;height:10px;border:2px solid var(--ink-900);flex-shrink:0}
.plegend .r b{margin-left:auto;color:var(--ink-900)}
/* 时段热力 */
.heat{display:flex;gap:2px}
.heat i{flex:1;height:20px;border:1px solid var(--ink-900);background:var(--surface-card);cursor:pointer;transition:transform .1s}
.heat i:hover{transform:scale(1.18);outline:2px solid #d3212c;outline-offset:1px}
.heat i.l1{background:#f0dc7a}
.heat i.l2{background:#f5c400}
.heat i.l3{background:#d3212c}
.heat i.picked{outline:2px solid #d3212c;outline-offset:1px}
.heatx{display:flex;justify-content:space-between;font-size:7.5px;color:var(--ink-400);margin-top:3px;font-weight:700}
/* 驱离执行读数 */
.gauge{display:flex;align-items:center;gap:12px}
.gauge .num b{font-size:30px;font-weight:700;color:var(--ink-900)}
.gauge .num span{display:block;font-size:8.5px;color:var(--ink-400);letter-spacing:2px;margin-top:2px}
.gauge .mini{flex:1;display:flex;flex-direction:column;gap:5px;min-width:0}
.gauge .mini .r{display:flex;justify-content:space-between;gap:6px;font-size:9.5px;border-bottom:1px solid var(--ink-300);padding-bottom:3px;color:var(--ink-700)}
.gauge .mini .r.last{border-bottom:0}
.gauge .mini .r b{font-weight:700;color:var(--ink-900);text-align:right}
@media (prefers-reduced-motion: reduce){
  .linewrap .mk,.heat i,.pie .slice,.pie .slice circle,.rank .track i{transition:none !important}
  .linewrap .mk:hover,.heat i:hover{transform:none}
}
</style>
