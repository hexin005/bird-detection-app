<script setup lang="ts">
// 果园害鸟图鉴(大视图,预览批次 docs/ui-flow/guide.html 方案):
// 两列图片网格,封面依次取自选图、本园抓拍和剪影;
// 点卡片开详情浮层(影响/识别/时段/应对);「查看该鸟告警」跳告警页并按物种过滤(host.alarmSpecies)。
import { computed, ref, watch } from 'vue'
import { useHost } from '../hostContext'
import { useOrchard } from '../../../store'
import { SPECIES_GUIDE, LEVEL_META, type GuideLevel, type SpeciesInfo } from '../../../data/speciesGuide'

const host = useHost()
const store = useOrchard()
const groups = ref<Record<string, { cover?: string; total: number }>>({})
const customImages = ref<string[]>([])
const customFailed = ref<Record<string, boolean>>({})
const captureFailed = ref<Record<string, boolean>>({})
const openInfo = ref<SpeciesInfo | null>(null)

const grouped = computed(() => (['high', 'mid', 'low'] as GuideLevel[]).map(level => ({
  level, ...LEVEL_META[level], items: SPECIES_GUIDE.filter(s => s.level === level),
})))

async function loadCovers() {
  customFailed.value = {}
  captureFailed.value = {}
  try {
    const data = await store.request<{ alarm_groups: { species: string; total: number; cover?: string }[]; guide_images: string[] }>('/library?offset=0')
    const map: Record<string, { cover?: string; total: number }> = {}
    for (const g of data.alarm_groups || []) map[g.species] = { cover: g.cover, total: g.total }
    groups.value = map
    customImages.value = data.guide_images || []
  } catch { /* 拉不到分组时全部走剪影占位 */ }
}
watch(() => host.page, page => { if (page === 'guide') void loadCovers() }, { immediate: true })

const hasCustom = (s: SpeciesInfo) => customImages.value.includes(s.name) && !customFailed.value[s.name]
const coverOf = (s: SpeciesInfo) => hasCustom(s) ? store.media('species-images/' + encodeURIComponent(s.name))
  : groups.value[s.name]?.cover && !captureFailed.value[s.name] ? store.media('captures/' + groups.value[s.name].cover) : ''
const coverLabel = (s: SpeciesInfo) => hasCustom(s) ? '自选图鉴照片' : '本园抓拍'
function imageFailed(s: SpeciesInfo) {
  if (hasCustom(s)) customFailed.value = { ...customFailed.value, [s.name]: true }
  else captureFailed.value = { ...captureFailed.value, [s.name]: true }
}
const totalOf = (s: SpeciesInfo) => groups.value[s.name]?.total ?? 0

function viewAlarms(s: SpeciesInfo) {
  openInfo.value = null
  host.viewSpeciesAlarms(s.name)
}
</script>

<template>
  <view class="qh-header">
    <view class="qh-header__brand">
      <text class="qh-page-title">果园害鸟图鉴</text>
      <text class="qh-page-subtitle">模型可识别 13 种 · 自选照片优先，其次本园抓拍</text>
    </view>
  </view>

  <template v-for="group in grouped" :key="group.level">
    <view class="sg-gbar" :class="'sg-gbar--' + group.level"><text>{{ group.groupTitle }}</text></view>
    <view class="sg-grid">
      <view v-for="s in group.items" :key="s.name" class="sg-card" :class="{ 'sg-card--dim': s.level === 'low' }" @click="openInfo = s">
        <view class="sg-photo" :class="{ 'sg-photo--empty': !coverOf(s) }">
          <image v-if="coverOf(s)" class="sg-img" :src="coverOf(s)" mode="aspectFill" @error="imageFailed(s)"/>
          <svg v-else width="46" height="46" viewBox="0 0 52 52" class="sg-bird"><path d="M14 38 C11 24 22 17 30 19 C32 11 42 9 46 13 L52 15 46 19 C48 28 42 37 31 38 L22 43 24 37 Z"/><circle cx="38" cy="15" r="1.6" fill="#111"/></svg>
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

  <text class="sg-note">分级与介绍为科普参考 · 封面优先使用自选照片，未设置时使用告警抓拍</text>

  <!-- 详情浮层 -->
  <view v-if="openInfo" class="qh-mask qh-mask--bottom is-open" @click.self="openInfo = null">
    <scroll-view scroll-y class="qh-sheet">
      <view class="qh-sheet__grab"/>
      <view class="qh-sheet__titlerow">
        <view><text class="qh-sheet__title">{{ openInfo.name }} · {{ openInfo.en }}</text>
          <text style="display:block;font-size:var(--text-xs);color:var(--ink-400);margin-top:3px">{{ LEVEL_META[openInfo.level].label }} · {{ openInfo.hours }}</text></view>
        <view class="qh-iconbtn--sm" @click="openInfo = null"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></view>
      </view>

      <view class="sg-big" :class="{ 'sg-big--empty': !coverOf(openInfo) }">
        <image v-if="coverOf(openInfo)" class="sg-big__img" :src="coverOf(openInfo)" mode="aspectFill" @error="imageFailed(openInfo)"/>
        <svg v-else width="96" height="96" viewBox="0 0 52 52" class="sg-bird"><path d="M14 38 C11 24 22 17 30 19 C32 11 42 9 46 13 L52 15 46 19 C48 28 42 37 31 38 L22 43 24 37 Z"/><circle cx="38" cy="15" r="1.6" fill="#111"/></svg>
        <text v-if="coverOf(openInfo)" class="sg-big__cap">{{ coverLabel(openInfo) }}</text>
      </view>

      <view class="sg-sec"><text class="sg-sec__h">对果园的影响</text><text class="sg-sec__p">{{ openInfo.harm }}</text></view>
      <view class="sg-sec"><text class="sg-sec__h">识别特征</text><text class="sg-sec__p">{{ openInfo.traits }}</text></view>
      <view class="sg-sec"><text class="sg-sec__h">活动时段</text><text class="sg-sec__p">{{ openInfo.hours }}</text></view>
      <view class="sg-sec"><text class="sg-sec__h">本园应对</text><text class="sg-sec__p">{{ openInfo.advice }}</text></view>

      <view class="sg-sheetfoot">
        <text class="sg-sheetfoot__his">本园历史告警 {{ totalOf(openInfo) }} 条</text>
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
.sg-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 14px}
.sg-card{background:var(--surface-card);border:2px solid var(--ink-900);box-shadow:3px 3px 0 var(--shadow-ink);padding:5px;cursor:pointer}
.sg-card--dim{border-style:dashed;box-shadow:none}
.sg-photo{height:92px;border:2px solid var(--ink-900);background:var(--surface-video);position:relative;display:flex;align-items:center;justify-content:center;overflow:hidden}
.sg-photo--empty{background:var(--surface-sunken);background-image:var(--dither-light)}
.sg-img{width:100%;height:100%}
.sg-bird{fill:var(--surface-card);opacity:.85}
.sg-photo__cap,.sg-photo__none{position:absolute;bottom:0;left:0;right:0;background:var(--ink-900);color:var(--surface-card);font-size:var(--text-2xs);padding:1px 5px;letter-spacing:1px}
.sg-photo__none{text-align:center;color:var(--ink-500);background:transparent}
.sg-card__row{display:flex;align-items:center;justify-content:space-between;gap:4px;margin-top:5px;padding:0 1px}
.sg-name{font-size:var(--text-md);font-weight:700;white-space:nowrap}
.sg-badge{border:2px solid var(--ink-900);font-size:var(--text-2xs);font-weight:700;padding:0 6px;letter-spacing:1px;white-space:nowrap}
.sg-badge--high{background:var(--warn-bg);color:var(--warn-fg)}
.sg-badge--mid{background:var(--surface-card)}
.sg-badge--low{border-color:var(--neutral-line);color:var(--neutral-fg)}
.sg-desc{display:block;font-size:var(--text-2xs);color:var(--ink-400);margin-top:3px;padding:0 1px 2px;line-height:var(--leading-snug)}
.sg-note{display:block;font-size:var(--text-2xs);color:var(--ink-300);margin:12px 14px 6px;line-height:var(--leading-normal)}
.sg-big{height:150px;border-bottom:2px solid var(--ink-900);background:var(--surface-video);position:relative;display:flex;align-items:center;justify-content:center;overflow:hidden}
.sg-big--empty{background:var(--surface-sunken);background-image:var(--dither-light)}
.sg-big__img{width:100%;height:100%}
.sg-big__cap{position:absolute;bottom:0;left:0;right:0;background:var(--ink-900);color:var(--surface-card);font-size:var(--text-xs);padding:2px 8px;letter-spacing:1px}
.sg-sec{padding:9px 11px 0}
.sg-sec__h{display:block;font-size:var(--text-2xs);font-weight:700;letter-spacing:var(--tracking-caps);color:var(--ink-400);border-bottom:1px solid var(--line-soft);padding-bottom:2px;margin-bottom:4px}
.sg-sec__p{display:block;font-size:var(--text-sm);color:var(--ink-800);line-height:var(--leading-normal)}
.sg-sheetfoot{display:flex;align-items:center;gap:8px;border-top:2px dashed var(--line-soft);padding:10px 11px;margin-top:10px}
.sg-sheetfoot__his{flex:1;font-size:var(--text-xs);color:var(--ink-500)}
.sg-sheetfoot__btn{border:2px solid var(--ink-900);background:var(--accent);color:var(--accent-fg);font-size:var(--text-sm);font-weight:700;padding:7px 11px;box-shadow:2px 2px 0 var(--shadow-ink);cursor:pointer}
</style>
