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
    alarms: Object.values(result.breakdown).reduce((sum, n) => sum + n, 0),
    rate: result.exec.total ? Math.round(result.exec.completed / result.exec.total * 100) : 0,
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
const daily = computed(() => {
  const data = stats.value
  if (!data) return []
  const taskTrend = data.task_trend || []
  const birdTrend = data.bird_trend || []
  const maxSessions = Math.max(1, ...taskTrend)
  const maxBirds = Math.max(1, ...birdTrend)
  return data.dates.map((date, index) => ({
    date, sessions: taskTrend[index] || 0, birds: birdTrend[index] || 0,
    alarms: data.trend[index] || 0,
    sessionHeight: data.task_trend[index] ? Math.max(6, Math.round(data.task_trend[index] / maxSessions * 100)) : 0,
    birdHeight: data.bird_trend[index] ? Math.max(6, Math.round(data.bird_trend[index] / maxBirds * 100)) : 0,
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
const rangeDates = computed(() => stats.value?.dates.length ? `${stats.value.dates[0]} ~ ${stats.value.dates[stats.value.dates.length - 1]}` : '')
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
  const filename = `orchard-stats-${range.value}-${data.dates[data.dates.length - 1]?.replace(/-/g, '') || 'today'}`
  let content: string, mime: string
  if (exportFormat.value === 'json') {
    content = JSON.stringify({ range: range.value, ...data }, null, 2)
    mime = 'application/json;charset=utf-8'
  } else {
    const taskTrend = data.task_trend || [], birdTrend = data.bird_trend || []
    const rows: (string | number | null)[][] = [
      ['日期', '检测场次', '发现鸟数', '检测告警数'],
      ...data.dates.map((date, i) => [date, taskTrend[i] || 0, birdTrend[i] || 0, data.trend[i] || 0]),
      [], ['鸟种分布', '发现鸟数'], ...data.bird_species.map(item => [item.species, item.count]),
      [], ['时段', '告警数'], ...data.hourly.map((count, hour) => [String(hour).padStart(2, '0') + ':00', count]),
      [], ['告警状态', '数量'], ...Object.entries(data.breakdown),
      [], ['驱离执行', '数值'], ...Object.entries(data.exec),
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
const alarmTotal = computed(() => stats.value ? Object.values(stats.value.breakdown).reduce((sum, value) => sum + value, 0) : 0)
const signalDays = computed(() => {
  const values = stats.value?.trend || []
  const max = Math.max(1, ...values)
  return (stats.value?.dates || []).map((date, index) => ({
    date, count: values[index] || 0,
    height: values[index] ? Math.max(7, Math.round(values[index] / max * 100)) : 0,
  }))
})
const signalSpecies = computed(() => {
  const values = stats.value?.species || []
  const max = Math.max(1, ...values.map(item => item.count))
  return values.map(item => ({ ...item, width: Math.round(item.count / max * 100) }))
})
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
</script>

<template>
  <view class="qh-header">
    <view class="qh-header__brand">
      <text class="qh-page-title">果园数据分析</text>
      <text class="qh-page-subtitle">{{ isSignal ? '东区观察手册 · 按自然日统计告警' : '统计覆盖整个演示果园 · 自然日口径' }}</text>
    </view>
    <button v-if="isB" class="qh-an-export" :disabled="!stats || loading" @click="exportOpen = true">↓ 导出</button>
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
        <text class="qh-an-sub">每场每物种只取峰值 · 点物种名称查看图鉴</text>
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
    <view class="field-analysis">
      <view class="field-intro">
        <text class="field-index">OBSERVATION / {{ rangeLabel }}<text v-if="!loading && !error && stats"> · {{ rangeDates }}</text></text>
        <text class="field-title">鸟情观察</text>
        <text class="field-caption">本页按检测告警事件统计，每条告警记一次；不计归档视频的鸟只数。</text>
      </view>
      <view class="field-ranges" role="group" aria-label="统计时间范围">
        <button :class="{ on: range === 'today' }" @click="pick('today')">今日</button>
        <button :class="{ on: range === '7d' }" @click="pick('7d')">近 7 天</button>
        <button :class="{ on: range === '30d' }" @click="pick('30d')">近 30 天</button>
      </view>
      <view v-if="loading" class="field-feedback">正在读取 {{ rangeLabel }} 的统计数据…</view>
      <view v-else-if="error" class="field-feedback field-feedback--error">统计读取失败：{{ error }} <button @click="load">重试</button></view>
      <template v-else-if="stats && !loading">
        <view class="field-summary">
          <view class="field-total"><text>检测告警</text><strong>{{ alarmTotal }}</strong><small>条 · {{ rangeLabel }}</small></view>
          <view class="field-metrics">
            <view><b>{{ stats.breakdown.new }}</b><text>待处理 · 条</text></view>
            <view><b>{{ stats.exec.total }}</b><text>驱离执行 · 次</text></view>
            <view><b>{{ stats.exec.total ? Math.round(stats.exec.completed / stats.exec.total * 100) + '%' : '暂无' }}</b><text>执行完成率</text></view>
          </view>
        </view>
        <view class="field-panel">
          <view class="field-panel-head"><text>01 / 每日告警趋势</text><small>单位 · 条</small></view>
          <view v-if="alarmTotal" class="field-daychart" :class="{ dense: range === '30d' }">
            <button v-for="(day, index) in signalDays" :key="day.date" :class="{ picked: selectedDay === index }" :aria-label="`${day.date} ${day.count} 条告警`" @click="selectedDay = index">
              <i :style="{ height: day.height + '%' }"/><span v-if="range !== '30d' || index % 5 === 0 || index === signalDays.length - 1">{{ range === 'today' ? '今日' : day.date.slice(5) }}</span>
            </button>
          </view>
          <text v-else class="field-empty">本范围无告警；归档视频的检测记录可在“记录”页查看。</text>
          <text v-if="alarmTotal" class="field-detail">{{ selectedDay >= 0 && signalDays[selectedDay] ? `${signalDays[selectedDay].date} · ${signalDays[selectedDay].count} 条告警` : '点按日期查看当日告警条数' }}</text>
        </view>
        <view class="field-panel">
          <view class="field-panel-head"><text>02 / 告警物种</text><small>按告警条数 · TOP 5</small></view>
          <view v-if="signalSpecies.length" class="field-species">
            <view v-for="item in signalSpecies" :key="item.species" class="field-species-row">
              <button :disabled="!SPECIES_GUIDE.some(s => s.name === item.species)" @click="openGuide(item.species)">{{ item.species }}</button>
              <view class="track"><i :style="{ width: item.width + '%' }"/></view>
              <text>{{ item.count }} 条</text>
            </view>
          </view>
          <text v-else class="field-empty">本范围没有告警物种记录。</text>
          <text v-if="signalSpecies.length" class="field-detail">物种名称可打开图鉴；这里统计告警条数，不代表鸟只数。</text>
        </view>
        <view class="field-panel">
          <view class="field-panel-head"><text>03 / 24 小时活动</text><small>告警发生时段 · 条</small></view>
          <view v-if="alarmTotal" class="field-hours">
            <button v-for="(value, hour) in stats.hourly" :key="hour" :class="[heatLevel(value), { picked: selectedHour === hour }]" :aria-label="`${hour} 时 ${value} 条告警`" @click="selectedHour = hour"/>
          </view>
          <view v-if="alarmTotal" class="field-hours-label"><text>00</text><text>06</text><text>12</text><text>18</text><text>23</text></view>
          <text class="field-detail">{{ alarmTotal ? hourDetail : '本范围暂无时段告警数据' }}</text>
        </view>
        <view class="field-panel field-exec">
          <view class="field-panel-head"><text>04 / 驱离执行</text><small>模拟执行器</small></view>
          <view class="field-exec-row"><text>执行总数</text><b>{{ stats.exec.total }} 次</b></view>
          <view class="field-exec-row"><text>完成 / 失败</text><b>{{ stats.exec.completed }} / {{ stats.exec.failed }} 次</b></view>
          <view class="field-exec-row"><text>平均启动响应</text><b>{{ fmtSeconds(stats.exec.avg_start_seconds) }}</b></view>
          <text class="field-detail">没有执行时，响应与完成率仅展示原始统计，不推断驱离效果。</text>
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

  <text v-if="error" class="qh-note" style="display:block">{{ error }}</text>
  <text v-if="loading" class="qh-note">加载中…</text>
  <text class="qh-note">图表随主题联动换肤 · 数据来自果园服务实时统计</text>
  </template>

  <view v-if="isB && exportOpen" class="qh-mask qh-mask--bottom is-open" @click.self="exportOpen = false">
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
.field-analysis{display:flex;flex-direction:column;gap:12px;padding:0 1px 16px;color:var(--ink-900)}
.field-intro{display:flex;flex-direction:column;gap:5px;padding:15px 16px 13px;background:var(--surface-card);border:1px solid var(--line);border-radius:10px}
.field-index{font:700 10px var(--font-num);letter-spacing:2px;color:var(--accent)}
.field-title{font:800 22px var(--font-sans);letter-spacing:2px;color:var(--ink-900);text-shadow:0 0 16px rgba(127,224,168,.12)}
.field-caption{font-size:10px;line-height:1.5;color:var(--ink-500)}
.field-ranges{display:flex;gap:5px;padding:4px;border-radius:8px;background:var(--surface-sunken);border:1px solid var(--line)}
.field-ranges button{flex:1;border:0;border-radius:5px;min-height:34px;background:transparent;color:var(--ink-500);font-size:11px;cursor:pointer}
.field-ranges button.on{background:var(--surface-muted);color:var(--accent);font-weight:700;box-shadow:0 0 10px rgba(255,180,84,.15)}
.field-feedback{padding:10px 12px;background:var(--surface-muted);border-radius:6px;font-size:11px;color:var(--ink-500)}
.field-feedback--error{color:#ff6259}.field-feedback button{border:0;background:transparent;color:inherit;text-decoration:underline}
.field-summary{display:flex;gap:10px;padding:14px;background:var(--accent);border-radius:10px;color:var(--accent-fg);box-shadow:0 0 24px rgba(255,180,84,.22)}
.field-total{width:37%;display:flex;flex-direction:column;gap:2px;border-right:1px solid rgba(26,18,6,.3)}
.field-total text,.field-total small{font-size:10px}.field-total strong{font:700 43px/1.1 var(--font-num)}
.field-metrics{flex:1;display:flex;flex-direction:column;justify-content:space-between;gap:4px}.field-metrics view{display:flex;justify-content:space-between;align-items:baseline;gap:4px;border-bottom:1px solid rgba(26,18,6,.22)}
.field-metrics view:last-child{border:0}.field-metrics b{font:700 16px var(--font-num)}.field-metrics text{font-size:9px}
.field-panel{padding:13px 13px 14px;background:var(--surface-card);border:1px solid var(--line);border-radius:10px}
.field-panel-head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding-bottom:9px;border-bottom:1px solid var(--line-soft);color:var(--accent);font:700 12px var(--font-num);letter-spacing:1px}
.field-panel-head small{font:10px var(--font-sans);color:var(--ink-500);text-align:right;letter-spacing:0}
.field-daychart{display:flex;align-items:flex-end;gap:3px;height:110px;margin-top:13px;padding-bottom:19px;border-bottom:1px solid var(--line)}
.field-daychart button{flex:1;min-width:0;height:100%;border:0;background:transparent;display:flex;align-items:flex-end;justify-content:center;position:relative;cursor:pointer;padding:0}
.field-daychart i{width:75%;min-height:2px;background:var(--accent);border-radius:2px 2px 0 0;box-shadow:0 0 8px rgba(255,180,84,.45)}.field-daychart button.picked i{background:#ff6259;box-shadow:0 0 10px rgba(224,75,66,.55)}
.field-daychart span{position:absolute;bottom:-19px;left:50%;transform:translateX(-50%);white-space:nowrap;font:8px var(--font-num);color:var(--ink-500)}
.field-daychart.dense{gap:1px}.field-daychart.dense i{width:100%}.field-daychart.dense span{font-size:7px}
.field-detail{display:block;margin-top:10px;font-size:10px;line-height:1.5;color:var(--ink-500)}.field-empty{display:block;padding:22px 2px 9px;font-size:11px;line-height:1.6;color:var(--ink-500)}
.field-species{display:flex;flex-direction:column;gap:11px;padding-top:13px}.field-species-row{display:flex;align-items:center;gap:8px;min-width:0}
.field-species-row button{width:90px;flex-shrink:0;border:0;background:transparent;text-align:left;color:var(--accent);font-size:11px;overflow-wrap:anywhere;cursor:pointer;padding:0}.field-species-row button[disabled]{color:var(--ink-500);cursor:default}
.field-species-row .track{flex:1;height:7px;background:var(--surface-sunken);border-radius:6px;overflow:hidden}.field-species-row .track i{display:block;height:100%;background:var(--accent);border-radius:6px;box-shadow:0 0 8px rgba(255,180,84,.45)}
.field-species-row>text{width:38px;text-align:right;flex-shrink:0;font:10px var(--font-num);color:var(--ink-700)}
.field-hours{display:flex;gap:2px;margin-top:14px}.field-hours button{flex:1;height:26px;min-width:0;border:0;padding:0;border-radius:2px;cursor:pointer}
.field-hours .l0{background:var(--surface-sunken)}.field-hours .l1{background:rgba(255,180,84,.25)}.field-hours .l2{background:rgba(255,180,84,.55)}.field-hours .l3{background:var(--accent);box-shadow:0 0 8px rgba(255,180,84,.45)}.field-hours button.picked{outline:2px solid #ff6259;outline-offset:2px}
.field-hours-label{display:flex;justify-content:space-between;margin-top:5px;font:9px var(--font-num);color:var(--ink-500)}
.field-exec-row{display:flex;justify-content:space-between;align-items:baseline;padding:9px 1px;border-bottom:1px solid var(--line-soft);font-size:11px;color:var(--ink-700)}
.field-exec-row b{font:700 13px var(--font-num);color:var(--accent)}
</style>
