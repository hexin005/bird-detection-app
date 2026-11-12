<script setup lang="ts">
// 告警中心(A1 分诊台):最新一报大卡内联驱离/忽略;更早待处理压成单行;已处理折叠;物种 chips 常驻。
// 告警打开走 emit('open')(详情弹窗);内联驱离走 host.quickRepel(确认弹窗),忽略走 host.requestIgnore。
import { computed, ref, watch, onMounted } from 'vue'
import { useHost } from './host/hostContext'
import AlarmSpeciesPicker from './host/AlarmSpeciesPicker.vue'
import { useOrchard } from '../store'
import type { Alarm } from '../types'
const emit = defineEmits<{ open:[alarm:Alarm] }>()
const store = useOrchard()
const host = useHost()
// 物种过滤状态提升到 host(hostContext.alarmSpecies):图鉴「查看该鸟告警」等入口可外部设置
const species = computed(() => host.alarmSpecies)
const items = ref<Alarm[]>([])
const error = ref(''), doneError = ref(''), more = ref(false), loading = ref(false)
const doneOpen = ref(false), doneLoading = ref(false), doneItems = ref<Alarm[]>([])
/** 首屏只取 4 条，之后每次追 4 条 */
const PAGE = 4
let version = 0

const statusLabel: Record<string,string> = { new:'待处理', processing:'执行中', handled:'已处理', ignored:'已忽略' }
const shortTime = (v: number) => new Date(v * 1000).toLocaleString('zh-CN', { hour12:false, month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' })
const hero = computed(() => items.value[0] || null)
const rest = computed(() => items.value.slice(1))

async function load(append = false) {
  const current = ++version
  loading.value = true; error.value = ''
  try {
    const query = new URLSearchParams()
    query.set('pending','true')
    if (species.value) query.set('species', species.value)
    const alarms = await store.request<{items:Alarm[]}>('/alarm-list?' + query)
    if (current !== version) return
    const shown = append ? items.value.length + PAGE : PAGE
    items.value = alarms.items.slice(0, shown)
    more.value = alarms.items.length > shown
    if (doneOpen.value) void loadDone()
  } catch(e) {
    if (current === version) error.value = (e as Error).message
  } finally {
    if (current === version) loading.value = false
  }
}
/** 已处理/已忽略折叠区:展开时按当前筛选拉全量,过滤出已结条目 */
async function loadDone() {
  const current = version
  doneLoading.value = true; doneError.value = ''
  try {
    const query = new URLSearchParams()
    if (species.value) query.set('species', species.value)
    const all = await store.request<{items:Alarm[]}>('/alarm-list?' + query)
    if (current === version) doneItems.value = all.items.filter(a => a.status !== 'new' && a.status !== 'processing')
  } catch (e) {
    if (current === version) doneError.value = (e as Error).message
  } finally { if (current === version) doneLoading.value = false }
}
function toggleDone() {
  doneOpen.value = !doneOpen.value
  if (doneOpen.value && !doneItems.value.length) void loadDone()
}

watch(species, () => { items.value = []; doneItems.value = []; doneOpen.value = false; void load() })
watch(() => store.state?.counts.pending, () => { void load() })
onMounted(() => { void load() })
</script>
<template>
  <!-- 头部:标题 + 副标题 -->
  <view class="qh-header" style="position:relative;z-index:20">
    <view class="qh-header__brand">
      <text class="qh-page-title">告警中心</text>
      <text class="qh-page-subtitle">最新一报直接处置 · 待人工确认才会执行</text>
    </view>
  </view>

  <AlarmSpeciesPicker />

  <!-- 最新一报:大卡 + 内联动作 -->
  <view v-if="hero" class="qh-card al-hero">
    <view class="al-hero__hd">
      <text class="qh-badge qh-badge--new">最新一报</text>
      <text class="al-hero__meta mono">{{ shortTime(hero.at) }} · {{ hero.site }}</text>
    </view>
    <view class="al-hero__body" @click="emit('open', hero)">
      <image v-if="hero.snapshot" class="al-hero__thumb" :src="store.media('captures/' + hero.snapshot)" mode="aspectFill"/>
      <view v-else class="al-hero__thumb al-hero__thumb--empty"><text>♪</text></view>
      <view class="al-hero__info">
        <text class="al-hero__title">{{ hero.species }} ×{{ hero.count }}</text>
        <text class="al-hero__stat mono">录像 {{ hero.video_time.toFixed(1) }} 秒 · 置信 {{ (hero.confidence * 100).toFixed(0) }}%</text>
      </view>
    </view>
    <view class="al-hero__actions">
      <view class="al-act al-act--main" @click="host.quickRepel(hero.id)">▶ 驱离</view>
      <view class="al-act" @click="host.run(() => host.requestIgnore(hero.id))">忽略</view>
    </view>
  </view>

  <!-- 更早待处理:单行紧凑 -->
  <view v-if="rest.length" class="al-sectionlabel">更早待处理 · {{ rest.length }}</view>
  <view v-for="item in rest" :key="item.id" class="qh-card al-row" style="cursor:pointer" @click="emit('open', item)">
    <image v-if="item.snapshot" class="al-row__thumb" :src="store.media('captures/' + item.snapshot)" mode="aspectFill"/>
    <view v-else class="al-row__thumb al-row__thumb--empty"><text>♪</text></view>
    <view class="al-row__mid">
      <text class="al-row__title">{{ item.species }} · {{ item.count }} 只</text>
      <text class="al-row__meta mono">{{ shortTime(item.at) }} · {{ (item.confidence * 100).toFixed(0) }}%</text>
    </view>
    <text class="qh-badge" :class="'qh-badge--' + item.status">{{ statusLabel[item.status] }}</text>
    <text class="al-chevron">›</text>
  </view>

  <!-- 已处理/已忽略折叠 -->
  <view class="qh-card al-donebar" @click="toggleDone">
    <text class="al-donebar__t">已处理与已忽略</text>
    <text class="al-donebar__s">{{ doneOpen ? '收起 ▴' : (doneLoading ? '加载中…' : '展开 ▾') }}</text>
  </view>
  <template v-if="doneOpen">
    <view v-for="item in doneItems" :key="item.id" class="qh-card al-row al-row--done" style="cursor:pointer" @click="emit('open', item)">
      <image v-if="item.snapshot" class="al-row__thumb" :src="store.media('captures/' + item.snapshot)" mode="aspectFill"/>
      <view class="al-row__mid">
        <text class="al-row__title">{{ item.species }} · {{ item.count }} 只</text>
        <text class="al-row__meta mono">{{ shortTime(item.at) }}</text>
      </view>
      <text class="qh-badge" :class="'qh-badge--' + item.status">{{ statusLabel[item.status] }}</text>
    </view>
    <view v-if="doneError" style="padding:10px 14px"><text class="qh-note">历史告警读取失败：{{ doneError }} </text><text class="qh-note" @click="loadDone">重试</text></view>
    <view v-else-if="!doneItems.length && !doneLoading" style="padding:10px 0;text-align:center"><text class="qh-note">该范围暂无已处理记录</text></view>
  </template>

  <!-- 加载更多:分页而非一次渲染全部 -->
  <button v-if="more" class="qh-btn qh-btn--secondary qh-btn--sm al-more" :disabled="loading" @click="load(true)">
    {{ loading ? '加载中…' : '加载更多待处理' }}
  </button>

  <view v-if="!items.length && !loading && !error" style="padding:40px 0;text-align:center">
    <text class="qh-note">{{ species ? '该鸟种暂无进行中告警，可展开下方查看历史' : '当前没有待处理告警' }}</text>
  </view>

  <text v-if="error" class="qh-note" style="display:block">告警读取失败：{{ error }} <text @click="load()">重试</text></text>
</template>

<style scoped>
/* 最新一报 hero */
.al-hero{padding:0;overflow:hidden}
.al-hero__hd{display:flex;align-items:center;gap:10px;padding:8px 12px;border-bottom:2px solid var(--ink-900)}
.al-hero__meta{font-size:10px;color:var(--ink-400);letter-spacing:1px}
.al-hero__body{display:flex;gap:12px;padding:12px;cursor:pointer}
.al-hero__thumb{width:96px;height:96px;border:2px solid var(--ink-900);object-fit:cover;flex-shrink:0}
.al-hero__thumb--empty{display:flex;align-items:center;justify-content:center;background:var(--stripe);font-size:20px;color:var(--ink-400)}
.al-hero__info{flex:1;display:flex;flex-direction:column;justify-content:center;gap:5px;min-width:0}
.al-hero__title{font-size:16px;font-weight:800;color:var(--ink-900)}
.al-hero__stat{font-size:11px;color:var(--ink-400)}
.al-hero__actions{display:flex;border-top:2px solid var(--ink-900)}
.al-act{flex:1;display:flex;align-items:center;justify-content:center;padding:11px 0;font-size:14px;font-weight:800;letter-spacing:2px;color:var(--ink-900);background:var(--surface-card);cursor:pointer}
.al-act--main{flex:1.4;background:var(--ink-900);color:var(--surface-card);border-right:2px solid var(--ink-900)}
/* 更早待处理紧凑行 */
.al-sectionlabel{display:block;font-size:11px;font-weight:800;letter-spacing:2px;color:var(--ink-400);margin:14px 16px 6px}
.al-row{display:flex;align-items:center;gap:9px;padding:7px 11px;margin:0 14px 8px}
.al-row__thumb{width:40px;height:40px;border:2px solid var(--ink-900);object-fit:cover;flex-shrink:0}
.al-row__thumb--empty{display:flex;align-items:center;justify-content:center;background:var(--stripe);color:var(--ink-400)}
.al-row__mid{flex:1;min-width:0}
.al-row__title{display:block;font-size:12.5px;font-weight:800;color:var(--ink-900)}
.al-row__meta{display:block;font-size:10px;color:var(--ink-400);margin-top:2px}
.al-row--done{opacity:.75}
.al-chevron{color:var(--ink-400);font-size:14px}
/* 已处理折叠 */
.al-donebar{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;margin:12px 14px 8px;cursor:pointer}
.al-donebar__t{font-size:12.5px;font-weight:800;color:var(--ink-900)}
.al-donebar__s{font-size:11px;color:var(--ink-400)}
.al-more{width:calc(100% - 28px);margin:8px 14px 4px}
</style>
