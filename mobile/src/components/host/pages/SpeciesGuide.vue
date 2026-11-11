<script setup lang="ts">
// 鸟类知识库(图鉴升级版):数据来自 /api/knowledge(backend/knowledge.py 为权威源,
// 含档案扩展字段与本园记录聚合);请求失败回落 data/speciesGuide.ts 静态兜底,
// fallback 态下本园统计"不可用"而非 0。搜索按名称/学名/科属即时过滤。
// 点卡片开详情弹层:档案头(保护徽标) → 档案网格 → 本园记录(统计 + 24h 分布) → 知识分区;
// 「查看该鸟告警」跳告警页并按物种过滤(host.alarmSpecies)。
import { computed, ref, watch } from 'vue'
import { useHost } from '../hostContext'
import { useOrchard } from '../../../store'
import { SPECIES_GUIDE, LEVEL_META, type GuideLevel } from '../../../data/speciesGuide'
import type { KnowledgeSource, SpeciesKnowledge } from '../../../types'

const host = useHost()
const store = useOrchard()
const source = ref<KnowledgeSource>('loading')
const items = ref<SpeciesKnowledge[]>([])
const customImages = ref<string[]>([])
const customFailed = ref<Record<string, boolean>>({})
const captureFailed = ref<Record<string, boolean>>({})
const openName = ref('')
const query = ref('')

let version = 0
async function loadKnowledge() {
  const current = ++version
  source.value = 'loading'
  customFailed.value = {}
  captureFailed.value = {}
  try {
    const data = await store.request<{ items: SpeciesKnowledge[]; guide_images: string[] }>('/knowledge')
    if (current !== version) return
    items.value = data.items
    customImages.value = data.guide_images || []
    source.value = 'api'
  } catch {
    // 拉不到接口时回落内置静态知识:记录块显示"暂不可用",绝不把失败渲染成 0
    if (current !== version) return
    items.value = SPECIES_GUIDE.map(s => ({
      name: s.name, en: s.en, scientific_name: null, family: null,
      domestic_protection: null, iucn_status: null, level: s.level,
      desc: s.desc, harm: s.harm, traits: s.traits, hours: s.hours, advice: s.advice,
      voice: null, diet: null, ecology: null,
      records: { total: 0, pending: 0, last_seen: null, cover: null, best_confidence: null, videos: 0, peak_count: 0, first_seen: null, hour_buckets: Array(24).fill(0) },
    }))
    customImages.value = []
    source.value = 'fallback'
  }
}

watch(() => [host.page, host.guideSpecies] as const, ([page, species]) => {
  if (page !== 'guide') return
  void loadKnowledge()
  if (species) {
    openName.value = species
    host.guideSpecies = ''
  }
}, { immediate: true })

const queryTrimmed = computed(() => query.value.trim().toLowerCase())
const filtered = computed(() => {
  const q = queryTrimmed.value
  if (!q) return items.value
  return items.value.filter(s => [s.name, s.en, s.scientific_name, s.family].some(v => (v || '').toLowerCase().includes(q)))
})
const grouped = computed(() => (['high', 'mid', 'low'] as GuideLevel[]).map(level => ({
  level, ...LEVEL_META[level], items: filtered.value.filter(s => s.level === level),
})))
const displayGroups = computed(() => queryTrimmed.value
  ? [{ level: 'all' as GuideLevel | 'all', groupTitle: `搜索结果 · ${filtered.value.length} 种`, items: filtered.value }]
  : grouped.value)
const openInfo = computed(() => items.value.find(s => s.name === openName.value) || null)
const recordsReady = computed(() => source.value === 'api')
const hasRecords = (s: SpeciesKnowledge) => s.records.total > 0 || s.records.videos > 0

const hasCustom = (s: SpeciesKnowledge) => customImages.value.includes(s.name) && !customFailed.value[s.name]
const coverOf = (s: SpeciesKnowledge) => hasCustom(s) ? store.media('species-images/' + encodeURIComponent(s.name))
  : s.records.cover && !captureFailed.value[s.name] ? store.media('captures/' + s.records.cover) : ''
const coverLabel = (s: SpeciesKnowledge) => hasCustom(s) ? '自选图鉴照片' : '本园抓拍'
function imageFailed(s: SpeciesKnowledge) {
  if (hasCustom(s)) customFailed.value = { ...customFailed.value, [s.name]: true }
  else captureFailed.value = { ...captureFailed.value, [s.name]: true }
}
function previewCover(s: SpeciesKnowledge) {
  const url = coverOf(s)
  if (url) uni.previewImage({ urls: [url], current: url })
}

function ago(ts: number | null): string {
  if (!ts) return '—'
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 30 * 86400) return `${Math.floor(diff / 86400)} 天前`
  return new Date(ts * 1000).toLocaleDateString('zh-CN')
}
const maxBucket = computed(() => Math.max(1, ...(openInfo.value?.records.hour_buckets || [0])))
const barHeight = (n: number) => `${Math.round((n / maxBucket.value) * 100)}%`
const percent = (v: number | null) => v ? Math.round(v * 100) + '%' : '—'

function viewAlarms(s: SpeciesKnowledge) {
  openName.value = ''
  host.viewSpeciesAlarms(s.name)
}
</script>

<template>
  <view class="qh-header">
    <view class="qh-header__brand">
      <text class="qh-page-title">鸟类知识库</text>
      <text class="qh-page-subtitle">13 种园内鸟种 · 科普档案 + 本园记录</text>
    </view>
  </view>

  <view v-if="source === 'fallback'" class="sg-fallback">服务未连接 · 显示内置科普内容，本园记录暂不可用</view>

  <view class="sg-search">
    <view class="qh-input sg-search__field">
      <input v-model="query" type="text" placeholder="搜索名称 / 学名 / 科属" confirm-type="search"/>
    </view>
    <view v-if="query" class="sg-search__clear" @click="query = ''">清空</view>
  </view>

  <view v-if="source === 'loading'" class="sg-loading">知识库加载中…</view>
  <view v-else-if="filtered.length === 0" class="sg-empty">
    <text class="sg-empty__t">未找到相关鸟类</text>
    <text class="sg-empty__s">试试其他名称或学名</text>
    <view class="sg-empty__btn" @click="query = ''">清空搜索</view>
  </view>
  <template v-else>
    <template v-for="group in displayGroups" :key="group.level">
      <view class="sg-gbar" :class="'sg-gbar--' + group.level"><text>{{ group.groupTitle }}</text></view>
      <view class="sg-grid">
        <view v-for="s in group.items" :key="s.name" class="sg-card" :class="{ 'sg-card--dim': s.level === 'low' }" @click="openName = s.name">
          <view class="sg-photo" :class="{ 'sg-photo--empty': !coverOf(s) }">
            <image v-if="coverOf(s)" class="sg-img" :src="coverOf(s)" mode="aspectFill" @error="imageFailed(s)"/>
            <svg v-else width="46" height="46" viewBox="0 0 52 52" class="sg-bird"><path d="M14 38 C11 24 22 17 30 19 C32 11 42 9 46 13 L52 15 46 19 C48 28 42 37 31 38 L22 43 24 37 Z"/><circle cx="38" cy="15" r="1.6" fill="#111"/></svg>
            <text v-if="recordsReady && s.records.total > 0" class="sg-photo__count">本园 {{ s.records.total }}</text>
            <text v-if="coverOf(s)" class="sg-photo__cap">{{ coverLabel(s) }}</text>
            <text v-else class="sg-photo__none">暂无抓拍</text>
          </view>
          <view class="sg-card__row">
            <text class="sg-name">{{ s.name }}</text>
            <text class="sg-badge" :class="'sg-badge--' + s.level">{{ LEVEL_META[s.level].label }}</text>
          </view>
          <text class="sg-desc">{{ s.desc }}</text>
        </view>
      </view>
    </template>
  </template>

  <text class="sg-note">分级与介绍为科普参考 · 封面优先使用自选照片，未设置时使用告警抓拍</text>

  <!-- 详情弹层 -->
  <view v-if="openInfo" class="qh-mask qh-mask--bottom is-open" @click.self="openName = ''">
    <scroll-view scroll-y class="qh-sheet">
      <view class="qh-sheet__grab"/>
      <view class="qh-sheet__titlerow">
        <view style="min-width:0">
          <text class="qh-sheet__title">{{ openInfo.name }} · {{ openInfo.en }}</text>
          <text style="display:block;font-size:var(--text-xs);color:var(--ink-400);margin-top:3px">{{ LEVEL_META[openInfo.level].label }}</text>
        </view>
        <view class="qh-iconbtn--sm" @click="openName = ''"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></view>
      </view>

      <view class="sg-big" :class="{ 'sg-big--empty': !coverOf(openInfo) }" @click="previewCover(openInfo)">
        <image v-if="coverOf(openInfo)" class="sg-big__img" :src="coverOf(openInfo)" mode="aspectFill" @error="imageFailed(openInfo)"/>
        <svg v-else width="96" height="96" viewBox="0 0 52 52" class="sg-bird"><path d="M14 38 C11 24 22 17 30 19 C32 11 42 9 46 13 L52 15 46 19 C48 28 42 37 31 38 L22 43 24 37 Z"/><circle cx="38" cy="15" r="1.6" fill="#111"/></svg>
        <text v-if="coverOf(openInfo)" class="sg-big__cap">{{ coverLabel(openInfo) }} · 点击查看大图</text>
      </view>

      <view class="sg-badges">
        <text class="sg-badge" :class="'sg-badge--' + openInfo.level">{{ LEVEL_META[openInfo.level].label }}</text>
        <text v-if="openInfo.domestic_protection" class="sg-badge sg-badge--law">{{ openInfo.domestic_protection }}</text>
        <text v-if="openInfo.iucn_status" class="sg-badge sg-badge--law">IUCN {{ openInfo.iucn_status }}</text>
      </view>

      <view class="sg-profile">
        <view class="sg-profile__item"><text class="sg-profile__k">学名</text><text class="sg-profile__v sg-profile__v--italic">{{ openInfo.scientific_name || '—' }}</text></view>
        <view class="sg-profile__item"><text class="sg-profile__k">科属</text><text class="sg-profile__v">{{ openInfo.family || '—' }}</text></view>
        <view class="sg-profile__item"><text class="sg-profile__k">食性</text><text class="sg-profile__v">{{ openInfo.diet || '—' }}</text></view>
        <view class="sg-profile__item"><text class="sg-profile__k">活动时段</text><text class="sg-profile__v">{{ openInfo.hours }}</text></view>
      </view>

      <!-- 本园记录:统计不可用时明确说明,不渲染成 0 -->
      <view class="sg-rec" :class="{ 'sg-rec--empty': !recordsReady || !hasRecords(openInfo) }">
        <text class="sg-sec__h">本园记录</text>
        <text v-if="!recordsReady" class="sg-rec__na">本园记录暂不可用（服务未连接）</text>
        <text v-else-if="!hasRecords(openInfo)" class="sg-rec__na">暂无本园记录</text>
        <template v-else>
          <view class="sg-rec__stats">
            <view class="sg-rec__stat"><text class="sg-rec__n">{{ openInfo.records.total }}</text><text class="sg-rec__k">累计告警</text></view>
            <view class="sg-rec__stat"><text class="sg-rec__n">{{ openInfo.records.pending }}</text><text class="sg-rec__k">待处理</text></view>
            <view class="sg-rec__stat"><text class="sg-rec__n">{{ openInfo.records.videos }}</text><text class="sg-rec__k">档案视频</text></view>
            <view class="sg-rec__stat"><text class="sg-rec__n">{{ openInfo.records.peak_count }}</text><text class="sg-rec__k">单帧峰值</text></view>
          </view>
          <view class="sg-rec__row"><text class="sg-rec__label">最近出现</text><text class="sg-rec__value">{{ ago(openInfo.records.last_seen) }}</text></view>
          <view class="sg-rec__row"><text class="sg-rec__label">最佳置信度</text><text class="sg-rec__value">{{ percent(openInfo.records.best_confidence) }}</text></view>
          <text class="sg-rec__hist-h">活动时段分布 · 历史告警按小时聚合</text>
          <view class="sg-bars">
            <view v-for="(n, h) in openInfo.records.hour_buckets" :key="h" class="sg-bars__col">
              <view class="sg-bars__bar" :style="{ height: barHeight(n) }"/>
            </view>
          </view>
          <view class="sg-bars__axis"><text>0时</text><text>6时</text><text>12时</text><text>18时</text><text>23时</text></view>
        </template>
      </view>

      <view class="sg-sec"><text class="sg-sec__h">对果园的影响</text><text class="sg-sec__p">{{ openInfo.harm }}</text></view>
      <view class="sg-sec"><text class="sg-sec__h">识别特征</text><text class="sg-sec__p">{{ openInfo.traits }}</text></view>
      <view v-if="openInfo.voice" class="sg-sec"><text class="sg-sec__h">鸣声特点</text><text class="sg-sec__p">{{ openInfo.voice }}</text></view>
      <view v-if="openInfo.ecology" class="sg-sec"><text class="sg-sec__h">生态价值</text><text class="sg-sec__p">{{ openInfo.ecology }}</text></view>
      <view class="sg-sec"><text class="sg-sec__h">本园应对</text><text class="sg-sec__p">{{ openInfo.advice }}</text></view>

      <view class="sg-sheetfoot">
        <text class="sg-sheetfoot__his">{{ recordsReady ? `本园历史告警 ${openInfo.records.total} 条` : '本园历史告警暂不可用' }}</text>
        <view class="sg-sheetfoot__btn" @click="viewAlarms(openInfo)">查看该鸟告警</view>
      </view>
    </scroll-view>
  </view>
</template>

<style scoped>
.sg-gbar{display:flex;align-items:center;gap:8px;margin:14px 14px 6px;font-size:var(--text-xs);font-weight:700;letter-spacing:var(--tracking-caps)}
.sg-gbar::after{content:"";flex:1;height:2px;background:var(--ink-900)}
.sg-gbar--mid{color:var(--ink-600)}
.sg-gbar--low{color:var(--ink-400)}
.sg-fallback{margin:10px 14px 0;border:2px dashed var(--warn-fg);background:var(--warn-bg);color:var(--warn-fg);font-size:var(--text-2xs);padding:6px 10px;line-height:var(--leading-snug)}
.sg-search{display:flex;align-items:center;gap:8px;margin:12px 14px 2px}
.sg-search__field{flex:1;min-width:0}
.sg-search__clear{border:2px solid var(--ink-900);background:var(--surface-card);font-size:var(--text-2xs);font-weight:700;padding:6px 9px;cursor:pointer;white-space:nowrap}
.sg-loading{margin:18px 14px;border:2px dashed var(--line-soft);padding:22px 12px;text-align:center;font-size:var(--text-sm);color:var(--ink-400)}
.sg-empty{margin:18px 14px;border:2px dashed var(--line-soft);padding:22px 12px;text-align:center}
.sg-empty__t{display:block;font-size:var(--text-md);font-weight:700;color:var(--ink-600)}
.sg-empty__s{display:block;font-size:var(--text-xs);color:var(--ink-400);margin-top:4px}
.sg-empty__btn{display:inline-block;margin-top:10px;border:2px solid var(--ink-900);background:var(--surface-card);font-size:var(--text-xs);font-weight:700;padding:6px 12px;cursor:pointer;box-shadow:2px 2px 0 var(--shadow-ink)}
.sg-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 14px}
.sg-card{background:var(--surface-card);border:2px solid var(--ink-900);box-shadow:3px 3px 0 var(--shadow-ink);padding:5px;cursor:pointer}
.sg-card--dim{border-style:dashed;box-shadow:none}
.sg-photo{height:92px;border:2px solid var(--ink-900);background:var(--surface-video);position:relative;display:flex;align-items:center;justify-content:center;overflow:hidden}
.sg-photo--empty{background:var(--surface-sunken);background-image:var(--dither-light)}
.sg-img{width:100%;height:100%}
.sg-bird{fill:var(--surface-card);opacity:.85}
.sg-photo__cap,.sg-photo__none{position:absolute;bottom:0;left:0;right:0;background:var(--ink-900);color:var(--surface-card);font-size:var(--text-2xs);padding:1px 5px;letter-spacing:1px}
.sg-photo__none{text-align:center;color:var(--ink-500);background:transparent}
.sg-photo__count{position:absolute;top:0;right:0;background:var(--accent);color:var(--accent-fg);font-size:var(--text-2xs);font-weight:700;padding:1px 5px;letter-spacing:1px}
.sg-card__row{display:flex;align-items:center;justify-content:space-between;gap:4px;margin-top:5px;padding:0 1px}
.sg-name{font-size:var(--text-md);font-weight:700;white-space:nowrap}
.sg-badge{border:2px solid var(--ink-900);font-size:var(--text-2xs);font-weight:700;padding:0 6px;letter-spacing:1px;white-space:nowrap}
.sg-badge--high{background:var(--warn-bg);color:var(--warn-fg)}
.sg-badge--mid{background:var(--surface-card)}
.sg-badge--low{border-color:var(--neutral-line);color:var(--neutral-fg)}
.sg-badge--law{border-color:var(--neutral-line);color:var(--ink-600)}
.sg-desc{display:block;font-size:var(--text-2xs);color:var(--ink-400);margin-top:3px;padding:0 1px 2px;line-height:var(--leading-snug)}
.sg-note{display:block;font-size:var(--text-2xs);color:var(--ink-300);margin:12px 14px 6px;line-height:var(--leading-normal)}
.sg-big{height:150px;border-bottom:2px solid var(--ink-900);background:var(--surface-video);position:relative;display:flex;align-items:center;justify-content:center;overflow:hidden}
.sg-big--empty{background:var(--surface-sunken);background-image:var(--dither-light)}
.sg-big__img{width:100%;height:100%}
.sg-big__cap{position:absolute;bottom:0;left:0;right:0;background:var(--ink-900);color:var(--surface-card);font-size:var(--text-xs);padding:2px 8px;letter-spacing:1px}
.sg-badges{display:flex;flex-wrap:wrap;gap:6px;padding:9px 11px 0}
.sg-profile{display:grid;grid-template-columns:1fr 1fr;gap:8px 10px;padding:10px 11px 2px}
.sg-profile__item{border:1.5px solid var(--line-soft);padding:6px 8px;min-width:0}
.sg-profile__k{display:block;font-size:var(--text-2xs);letter-spacing:var(--tracking-caps);color:var(--ink-400);font-weight:700}
.sg-profile__v{display:block;font-size:var(--text-xs);color:var(--ink-800);margin-top:2px;line-height:var(--leading-snug);overflow-wrap:anywhere}
.sg-profile__v--italic{font-style:italic;font-family:var(--font-num)}
.sg-rec{border:2px solid var(--ink-900);background:var(--surface-sunken);margin:10px 11px 0;padding:8px 10px 10px}
.sg-rec--empty{border-style:dashed;box-shadow:none}
.sg-rec__na{display:block;font-size:var(--text-xs);color:var(--ink-400);padding:4px 0 2px}
.sg-rec__stats{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:8px}
.sg-rec__stat{background:var(--surface-card);border:1.5px solid var(--line-soft);padding:5px 4px;text-align:center}
.sg-rec__n{display:block;font-family:var(--font-num);font-size:var(--text-lg);font-weight:700;color:var(--ink-900)}
.sg-rec__k{display:block;font-size:var(--text-2xs);color:var(--ink-400);margin-top:1px}
.sg-rec__row{display:flex;justify-content:space-between;font-size:var(--text-xs);margin-top:7px}
.sg-rec__label{color:var(--ink-400)}
.sg-rec__value{color:var(--ink-800);font-weight:700}
.sg-rec__hist-h{display:block;margin-top:10px;font-size:var(--text-2xs);font-weight:700;letter-spacing:var(--tracking-caps);color:var(--ink-400)}
.sg-bars{display:flex;align-items:flex-end;gap:2px;height:44px;margin-top:6px}
.sg-bars__col{flex:1;height:100%;display:flex;align-items:flex-end}
.sg-bars__bar{width:100%;background:var(--accent);min-height:1px}
.sg-bars__axis{display:flex;justify-content:space-between;font-size:var(--text-2xs);color:var(--ink-300);margin-top:3px;font-family:var(--font-num)}
.sg-sec{padding:9px 11px 0}
.sg-sec__h{display:block;font-size:var(--text-2xs);font-weight:700;letter-spacing:var(--tracking-caps);color:var(--ink-400);border-bottom:1px solid var(--line-soft);padding-bottom:2px;margin-bottom:4px}
.sg-sec__p{display:block;font-size:var(--text-sm);color:var(--ink-800);line-height:var(--leading-normal)}
.sg-sheetfoot{display:flex;align-items:center;gap:8px;border-top:2px dashed var(--line-soft);padding:10px 11px;margin-top:10px}
.sg-sheetfoot__his{flex:1;font-size:var(--text-xs);color:var(--ink-500)}
.sg-sheetfoot__btn{border:2px solid var(--ink-900);background:var(--accent);color:var(--accent-fg);font-size:var(--text-sm);font-weight:700;padding:7px 11px;box-shadow:2px 2px 0 var(--shadow-ink);cursor:pointer}
</style>
