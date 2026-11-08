<script setup lang="ts">
import { computed, ref } from 'vue'
import { useOrchard } from '../store'
import type { Stats } from '../types'

const store = useOrchard()
const range = ref<'today' | '7d' | '30d'>('7d')
const stats = ref<Stats | null>(null)
const loading = ref(false), error = ref('')
const notify = (m: string) => uni.showToast({ title: m, icon: 'none', duration: 2500 })

async function load() {
  loading.value = true; error.value = ''
  try { stats.value = await store.request<Stats>('/stats?range=' + range.value) } catch (e) { error.value = (e as Error).message } finally { loading.value = false }
}
// 页面常驻 DOM,启动时未登录:不在此处加载,由 index.vue 在切入本页时触发 load()
defineExpose({ load })
function pick(next: 'today' | '7d' | '30d') { if (range.value !== next) { range.value = next; void load() } }

const counts = computed(() => ({
  events: stats.value?.breakdown ? stats.value.breakdown.new + stats.value.breakdown.processing + stats.value.breakdown.handled + stats.value.breakdown.ignored : 0,
  alarms: stats.value?.exec ? stats.value.exec.total : 0,
  exec: stats.value?.exec?.completed ?? 0,
}))
const buckets = computed(() => stats.value?.range_days ?? 7)
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
</script>

<template>
  <view class="qh-header">
    <view class="qh-header__brand">
      <text class="qh-page-title">果园数据分析</text>
      <text class="qh-page-subtitle">统计覆盖整个演示果园 · 自然日口径</text>
    </view>
  </view>

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
      <view class="qh-an-bignums" style="margin-top:0">
        <view><b>{{ stats?.exec.total ?? 0 }}</b><span>执行次数</span></view>
        <view><b>{{ stats?.exec.completed ?? 0 }}</b><span>完成</span></view>
        <view><b>{{ fmtSeconds(stats?.exec.avg_start_seconds) }}</b><span>平均启动响应</span></view>
      </view>
      <view class="qh-an-rate">
        <i :style="{ width: (stats?.exec.total ? Math.round((stats.exec.completed / stats.exec.total) * 100) : 0) + '%' }" />
        <b>完成率 {{ stats?.exec.total ? Math.round((stats.exec.completed / stats.exec.total) * 100) : 0 }}%</b>
      </view>
      <text class="qh-an-sub">平均完成耗时 <b>{{ fmtSeconds(stats?.exec.avg_done_seconds) }}</b> · 双模联动占 <b>{{ pctText(stats?.exec.dual_share) }}</b>(分母=已完成指令)· 失败 {{ stats?.exec.failed ?? 0 }} 次</text>
    </view>
  </view>

  <text v-if="error" class="qh-note" style="display:block">{{ error }} — {{ '' }}</text>
  <text v-if="loading" class="qh-note">加载中…</text>
  <text class="qh-note">图表随主题联动换肤 · 数据来自果园服务实时统计</text>
</template>
