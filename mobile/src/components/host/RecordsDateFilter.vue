<script setup lang="ts">
// 记录页挂绳日历(B/C 共用):顶部一根短绳挂一枚小牌,点牌日历垂下展开;
// 选某天=只看该日(写入 host.recordDate),清除恢复全部。面板内不做区间,保持轻量。
import { computed, ref } from 'vue'
import { useHost } from './hostContext'

const host = useHost()
const open = ref(false)
const now = new Date()
const viewYear = ref(now.getFullYear())
const viewMonth = ref(now.getMonth()) // 0-based

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'] as const

/** 当月格子:周日开头,前置空位 + 当月天数;每天带完整 recordDate 值 */
const cells = computed(() => {
  const first = new Date(viewYear.value, viewMonth.value, 1).getDay()
  const total = new Date(viewYear.value, viewMonth.value + 1, 0).getDate()
  const list: { day: number | null; value?: string }[] = []
  for (let i = 0; i < first; i++) list.push({ day: null })
  for (let d = 1; d <= total; d++) {
    list.push({ day: d, value: `${viewYear.value}-${String(viewMonth.value + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}` })
  }
  return list
})
const todayValue = computed(() => {
  const t = new Date()
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
})
/** 小牌文案:未选=icon+日期;已选=MM·DD(黄底) */
const tagText = computed(() => {
  if (!host.recordDate) return ''
  const [, m, d] = host.recordDate.split('-')
  return `${m}·${d}`
})
function shiftMonth(delta: number) {
  const next = new Date(viewYear.value, viewMonth.value + delta, 1)
  viewYear.value = next.getFullYear()
  viewMonth.value = next.getMonth()
}
function pick(value?: string) {
  if (!value) return
  host.recordDate = host.recordDate === value ? '' : value
  open.value = false
}
function clear() {
  host.recordDate = ''
  open.value = false
}
</script>

<template>
  <view class="rdf" :class="{ 'is-open': open }">
    <view class="rdf__rope"/>
    <view class="rdf__tag" :class="{ 'is-on': !!host.recordDate }" role="button"
      :aria-label="host.recordDate ? `日期筛选:${tagText},点击修改` : '按日期筛选记录'"
      @click="open = !open">
      <text v-if="host.recordDate" class="rdf__tagtext">{{ tagText }}</text>
      <template v-else>
        <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
          <rect x="1.5" y="2.5" width="11" height="10" stroke="currentColor" stroke-width="1.5"/>
          <path d="M1.5 5.5h11M4.5 1v3M9.5 1v3" stroke="currentColor" stroke-width="1.5"/>
        </svg>
        <text class="rdf__tagtext">日期</text>
      </template>
    </view>

    <view v-if="open" class="rdf__cal">
      <view class="rdf__hd">
        <view class="rdf__nav"><text class="rdf__arrow" @click="shiftMonth(-1)">‹</text><text class="rdf__ym">{{ viewYear }}年{{ viewMonth + 1 }}月</text><text class="rdf__arrow" @click="shiftMonth(1)">›</text></view>
        <view class="rdf__ops">
          <text v-if="host.recordDate" class="rdf__clear" @click="clear">清除筛选</text>
          <text class="rdf__x" aria-label="关闭日历" @click="open = false">✕</text>
        </view>
      </view>
      <view class="rdf__week"><text v-for="w in WEEKDAYS" :key="w">{{ w }}</text></view>
      <view class="rdf__grid">
        <view v-for="(c, i) in cells" :key="i" class="rdf__cell"
          :class="{ 'is-empty': !c.day, 'is-sel': c.value && c.value === host.recordDate, 'is-today': c.value && c.value === todayValue }"
          @click="pick(c.value)"><text v-if="c.day">{{ c.day }}</text></view>
      </view>
      <text class="rdf__hint">点某一天 = 只看该日 · 清除筛选恢复全部</text>
    </view>
  </view>
</template>

<style scoped>
.rdf{position:relative;display:flex;flex-direction:column;align-items:center;flex-shrink:0}
.rdf__rope{width:0;height:12px;border-left:2px dashed var(--ink-900)}
.rdf__tag{display:flex;align-items:center;gap:4px;border:2px solid var(--ink-900);background:var(--surface-card);color:var(--ink-900);font-size:10.5px;font-weight:800;letter-spacing:1px;padding:4px 8px;box-shadow:2px 2px 0 var(--shadow-ink);cursor:pointer;white-space:nowrap}
.rdf__tag:active{background:#f5c400}
.rdf__tag.is-on{background:#f5c400}
.rdf__tagtext{font-size:10.5px;font-weight:800;letter-spacing:1px}
/* 日历牌:从挂绳处垂下展开 */
.rdf__cal{position:absolute;top:calc(100% + 3px);right:-10px;width:288px;border:2px solid var(--ink-900);background:var(--surface-card);box-shadow:6px 8px 0 var(--shadow-ink);padding:9px 11px 11px;transform-origin:top center;transform:translateY(-10px);opacity:0;visibility:hidden;transition:transform .26s ease-out,opacity .22s ease-out,visibility .26s;z-index:80;cursor:default}
.is-open .rdf__cal{transform:none;opacity:1;visibility:visible}
.rdf__hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:7px}
.rdf__nav{display:flex;align-items:center;gap:2px}
.rdf__arrow{font-size:13px;font-weight:900;padding:0 6px;cursor:pointer;color:var(--ink-900)}
.rdf__ym{font-size:12.5px;font-weight:900;color:var(--ink-900)}
.rdf__ops{display:flex;align-items:center;gap:9px}
.rdf__clear{font-size:9.5px;font-weight:800;color:var(--accent);text-decoration:underline;cursor:pointer}
.rdf__x{font-size:10px;font-weight:900;border:2px solid var(--ink-900);width:18px;height:18px;display:flex;align-items:center;justify-content:center;color:var(--ink-900)}
.rdf__week,.rdf__grid{display:grid;grid-template-columns:repeat(7,1fr);gap:3px}
.rdf__week text{text-align:center;font-size:9px;font-weight:800;color:var(--ink-400);padding:2px 0}
.rdf__cell{height:31px;display:flex;align-items:center;justify-content:center;font-size:11.5px;font-weight:700;border:2px solid transparent;background:var(--surface-canvas);cursor:pointer;color:var(--ink-900)}
.rdf__cell:hover{border-color:var(--ink-900)}
.rdf__cell.is-empty{background:transparent;border:none;cursor:default}
.rdf__cell.is-sel{background:#f5c400;border-color:var(--ink-900)}
.rdf__cell.is-today{border-color:var(--accent)}
.rdf__hint{display:block;margin-top:7px;font-size:9px;color:var(--ink-400)}
</style>
