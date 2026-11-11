<script setup lang="ts">
// 一检一记:检测记录档案卡列表(方案 A)。数据 /api/library(前端过滤仅归档任务),
// 卡片只呈现「时间 + 检测结果(N 种 · M 只)」;展开 = 结果回放 + 本场处置线,完整执行链仍走告警详情/操作记录弹窗。
import { computed, ref, watch } from 'vue'
import { useHost, clock, modeCn, names } from './hostContext'
import VideoPlayer from '../VideoPlayer.vue'
import type { LibraryDetail, LibraryItem } from '../../types'

const host = useHost()
const props = defineProps<{ initialTask?: string; nonce?: number }>()

const items = ref<LibraryItem[]>([])
const expanded = ref(''), detail = ref<LibraryDetail | null>(null)
const loading = ref(false), loadingDetail = ref(false), error = ref(''), detailError = ref('')
const more = ref(false)
let version = 0, seenNonce = -2

/** 仅归档任务:ended(完整)与 stopped(部分归档)result_ready=1;running/error/interrupted 不进记录页 */
const archived = computed(() => items.value.filter(t => t.result_ready === 1))
const birdsOf = (item: LibraryItem) => item.species.reduce((sum, s) => sum + s.peak_count, 0)
const durText = (d: number) => d >= 60 ? `${Math.floor(d / 60)}分${String(Math.round(d % 60)).padStart(2, '0')}秒` : `${Math.round(d)}秒`

/** 按自然日分桶(items 已按 at DESC) */
const dayGroups = computed(() => {
  const now = new Date(), today = `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}`
  const groups: { key: string; label: string; items: LibraryItem[] }[] = []
  for (const item of archived.value) {
    const d = new Date(item.at * 1000)
    const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
    let g = groups.find(x => x.key === key)
    if (!g) { g = { key, label: key === today ? `${d.getMonth() + 1}月${d.getDate()}日 · 今天` : `${d.getMonth() + 1}月${d.getDate()}日`, items: [] }; groups.push(g) }
    g.items.push(item)
  }
  return groups
})

let offset = 0
async function load(append = false) {
  const current = ++version; loading.value = true
  try {
    const data = await host.store.request<{ items: LibraryItem[] }>(`/library?offset=${append ? offset : 0}`)
    if (current !== version) return
    // 偏移量按原始分页累计(列表经 result_ready 过滤后长度不等于原始页大小)
    offset = append ? offset + data.items.length : data.items.length
    items.value = append ? [...items.value, ...data.items] : data.items
    more.value = data.items.length === 30
    error.value = ''
  } catch (e) { if (current === version) error.value = (e as Error).message } finally { if (current === version) loading.value = false }
}

/** 深链展开:目标不在已加载分页时继续向后翻页查找(上限 10 页);展开后滚动定位到该卡 */
async function expandTask(id: string) {
  let guard = 0
  while (!items.value.find(t => t.id === id) && more.value && guard++ < 10) await load(true)
  const target = items.value.find(t => t.id === id)
  if (!target) return
  await toggle(target)
  if (typeof document !== 'undefined') {
    setTimeout(() => document.querySelector('.dr-card.is-open')?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 260)
  }
}

async function toggle(item: LibraryItem) {
  if (expanded.value === item.id) { expanded.value = ''; detail.value = null; detailError.value = ''; return }
  expanded.value = item.id; detail.value = null; detailError.value = ''
  loadingDetail.value = true
  try { detail.value = await host.store.request<LibraryDetail>('/library/' + item.id) }
  catch (e) { detailError.value = (e as Error).message } // 旧任务无档案:detail() 报"旧版本记录仅保留抓拍"
  finally { loadingDetail.value = false }
}

/** 本场处置线:告警行 + 该告警关联的指令摘要(指令快照取自 WS state 最近 100 条) */
const commandsOf = (alarmId: string) => (host.s?.commands || []).filter(c => c.alarm_id === alarmId)

// 进入记录页刷新;告警「回看视频」深链(replayAlarm):进入后自动展开对应任务
watch(() => [host.page, props.nonce ?? -2] as const, ([p, nonce]) => {
  if (p !== 'records') return
  const deep = nonce !== seenNonce && !!props.initialTask
  void load().then(() => {
    if (!deep) return
    seenNonce = nonce
    void expandTask(props.initialTask!)
  })
}, { immediate: true })
</script>

<template>
  <view v-for="day in dayGroups" :key="day.key">
    <view class="dr-daybar"><text>{{ day.label }}</text></view>

    <view v-for="item in day.items" :key="item.id" class="qh-card dr-card" :class="{ 'is-open': expanded === item.id }" @click="toggle(item)">
      <view class="dr-head">
        <text class="dr-time">{{ clock(item.at) }}</text>
        <text class="dr-dur">{{ durText(item.duration) }}</text>
        <text class="dr-sum" :class="{ 'is-zero': !item.species.length }">{{ item.species.length ? `${item.species.length} 种 · ${birdsOf(item)} 只` : '未发现鸟' }}</text>
      </view>
      <view class="qh-chips">
        <text v-for="bird in item.species" :key="bird.species" class="qh-chip">{{ bird.species }} ×{{ bird.peak_count }}</text>
        <text v-if="!item.species.length" class="qh-chip dr-chip--empty">无检出 · 已归档</text>
        <text v-if="item.status === 'stopped'" class="qh-chip dr-chip--part">部分归档</text>
      </view>

      <!-- 展开详情:结果回放 + 本场处置线 -->
      <view v-if="expanded === item.id" class="dr-detail" @click.stop>
        <view v-if="loadingDetail" class="dr-note">正在加载本场详情…</view>
        <template v-else-if="detail">
          <VideoPlayer v-if="detail.result_ready" :path="`media/${detail.id}/result.mp4`" class="dr-player"/>
          <VideoPlayer v-else-if="detail.stream_ready" :path="`media/${detail.id}/index.m3u8`" class="dr-player"/>
          <view v-else class="dr-note">{{ detail.message }}；当前没有可播放的结果视频。</view>
          <text class="dr-detail__label">本场处置线</text>
          <view v-for="a in detail.alarms" :key="a.id" class="dr-line">
            <text class="dr-line__t">{{ clock(a.at) }}</text>
            <view class="dr-line__body">
              <text class="dr-line__m">检测到 {{ a.species }} ×{{ a.count }} · {{ names(a.status) }}</text>
              <text v-for="c in commandsOf(a.id)" :key="c.id" class="dr-line__c">{{ modeCn[c.mode || 'both'] }} {{ c.duration }} 秒 · {{ names(c.status) }}</text>
            </view>
          </view>
          <text v-if="!detail.alarms?.length" class="dr-note">本场无告警 — 仅保留识别结果,可回看完整视频</text>
        </template>
        <view v-else class="dr-note">{{ detailError || '本场详情暂不可用' }}</view>
      </view>
    </view>
  </view>

  <view v-if="!archived.length && !loading" class="dr-empty">
    <text>还没有检测记录 — 从监控页导入视频并开始检测，一次检测会在这里生成一条记录</text>
  </view>
  <button v-if="more" class="qh-btn qh-btn--secondary qh-btn--sm dr-more" :disabled="loading" @click="load(true)">加载更早 ▾</button>
  <text v-if="error" class="qh-note dr-foot">{{ error }}</text>
  <text v-if="archived.length" class="dr-foot">一次检测 = 一条记录 · 告警与驱离的完整执行链在「告警页 / 操作记录」内查看</text>
</template>

<style scoped>
.dr-daybar{display:flex;align-items:center;gap:10px;margin:14px 14px 6px;font-size:var(--text-xs);font-weight:700;letter-spacing:var(--tracking-caps);color:var(--ink-600)}
.dr-daybar::before,.dr-daybar::after{content:"";flex:1;height:2px;background:var(--ink-900)}
.dr-card{margin:0 14px 8px;padding:10px 12px;cursor:pointer}
.dr-card.is-open{box-shadow:5px 5px 0 var(--shadow-ink)}
.dr-head{display:flex;align-items:baseline;gap:8px}
.dr-time{font-size:var(--text-lg);font-weight:700;font-family:var(--font-num)}
.dr-dur{font-size:var(--text-2xs);color:var(--ink-400);font-family:var(--font-num)}
.dr-sum{margin-left:auto;white-space:nowrap;border:2px solid var(--ink-900);background:var(--warn-bg);color:var(--warn-fg);font-size:var(--text-2xs);font-weight:700;padding:1px 7px;letter-spacing:1px}
.dr-sum.is-zero{background:var(--neutral-bg);color:var(--neutral-fg);border-color:var(--neutral-line)}
.qh-chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}
.dr-chip--empty{border-style:dashed;color:var(--ink-400);background:transparent}
.dr-chip--part{border-style:dashed;color:var(--ink-600)}
.dr-detail{margin-top:9px;border-top:2px solid var(--ink-900);padding-top:9px}
.dr-detail__label{display:block;font-size:var(--text-2xs);font-weight:700;letter-spacing:var(--tracking-caps);color:var(--ink-400);margin:9px 0 4px}
.dr-player{height:180px}
.dr-line{display:flex;gap:8px;padding:4px 0;border-bottom:1px solid var(--line-soft)}
.dr-line:last-of-type{border-bottom:none}
.dr-line__t{font-size:var(--text-xs);color:var(--ink-400);font-family:var(--font-num);white-space:nowrap;padding-top:1px}
.dr-line__body{display:flex;flex-direction:column;gap:2px}
.dr-line__m{font-size:var(--text-sm);color:var(--ink-800)}
.dr-line__c{font-size:var(--text-2xs);color:var(--ink-500)}
.dr-note{display:block;font-size:var(--text-xs);color:var(--ink-400);padding:6px 0;line-height:var(--leading-normal)}
.dr-empty{margin:24px 14px;border:2px dashed var(--neutral-line);padding:18px 12px;text-align:center}
.dr-empty text{font-size:var(--text-xs);color:var(--ink-400);line-height:var(--leading-normal)}
.dr-more{width:calc(100% - 28px);margin:4px 14px}
.dr-foot{display:block;font-size:var(--text-2xs);color:var(--ink-300);text-align:center;padding:10px 0 4px;line-height:var(--leading-normal)}
</style>
