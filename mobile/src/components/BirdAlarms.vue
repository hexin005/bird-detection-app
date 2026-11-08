<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useOrchard } from '../store'
import type { Alarm } from '../types'
const emit = defineEmits<{ open:[alarm:Alarm] }>()
const store = useOrchard()
const species = ref('')
const items = ref<Alarm[]>([])
type Group = { species:string; total:number; pending:number; cover?:string; best_confidence?:number }
const groups = ref<Group[]>([])
const error = ref(''), more = ref(false), loading = ref(false)
/** 首屏只取 4 条，之后每次追 4 条 */
const PAGE = 4
/** 下拉框展开状态 */
const open = ref(false)
let version = 0

const heading = computed(() => species.value || '全部待处理')

const statusLabel: Record<string,string> = { new:'待处理', processing:'执行中', handled:'已处理', ignored:'已忽略' }
const shortTime = (v: number) => new Date(v * 1000).toLocaleString('zh-CN', { hour12:false, month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' })

async function load(append = false) {
  const current = ++version
  loading.value = true; error.value = ''
  try {
    const query = new URLSearchParams()
    if (!species.value) query.set('pending','true')
    if (species.value) query.set('species', species.value)
    const [alarms, index] = await Promise.all([
      store.request<{items:Alarm[]}>('/alarm-list?' + query),
      store.request<{alarm_groups:Group[]}>('/library')
    ])
    if (current !== version) return
    const all = alarms.items
    const shown = append ? items.value.length + PAGE : PAGE
    items.value = all.slice(0, shown)
    more.value = all.length > shown
    groups.value = index.alarm_groups
  } catch(e) {
    error.value = (e as Error).message
  } finally {
    if (current === version) loading.value = false
  }
}

function toggle() { open.value = !open.value }
function pick(name: string) {
  species.value = name
  open.value = false
  items.value = []
  void load()
}
function reset() {
  species.value = ''
  items.value = []
  void load()
}

watch(() => store.state?.counts.pending, () => { void load() })
onMounted(() => { void load() })
</script>
<template>
  <!-- 头部：标题 + 下拉框触发按钮 -->
  <view class="qh-header" style="position:relative;z-index:20">
    <view class="qh-header__brand">
      <text class="qh-page-title">告警中心</text>
      <text class="qh-page-subtitle">待人工确认后，才会执行驱离</text>
    </view>
    <button class="qh-iconbtn" :class="{ 'is-open': open }" @click="toggle">
      <svg v-if="!open" width="22" height="20" viewBox="0 0 22 20" fill="none"><path d="M2 5h18M5 10h12M8 15h6" stroke="#111111" stroke-width="1.6" stroke-linecap="round"/></svg>
      <svg v-else width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2.5 2.5L11.5 11.5M11.5 2.5L2.5 11.5" stroke="#111111" stroke-width="1.6" stroke-linecap="round"/></svg>
    </button>
  </view>

  <!-- 下拉框：鸟类分类 -->
  <view v-if="open" class="qh-dropdown">
    <view class="qh-dropdown__head">
      <text class="qh-dropdown__title">按鸟类分类</text>
      <text v-if="species" class="qh-dropdown__reset" @click="reset">查看全部 ›</text>
    </view>
    <view class="qh-dropdown__list">
      <view
        v-for="g in groups"
        :key="g.species"
        class="qh-birdrow"
        :class="{ 'is-active': species === g.species }"
        @click="pick(g.species)"
      >
        <!-- 鸟类封面图 -->
        <image
          v-if="g.cover"
          class="qh-birdrow__cover"
          :src="store.media('captures/' + g.cover)"
          mode="aspectFill"
        />
        <view v-else class="qh-birdrow__cover qh-birdrow__cover--empty">
          <text style="font-size:16px;color:#111111">♪</text>
        </view>
        <view class="qh-birdrow__info">
          <text class="qh-birdrow__name">{{ g.species }}</text>
          <text class="qh-birdrow__stat">{{ g.total }} 条告警 · {{ g.pending }} 条待处理</text>
        </view>
        <text v-if="g.best_confidence" class="qh-birdrow__conf">{{ (g.best_confidence * 100).toFixed(0) }}%</text>
        <text class="qh-chevron">›</text>
      </view>
      <text v-if="!groups.length" class="qh-note" style="display:block;padding:24px 0;text-align:center">检测到鸟类后，会在这里自动分类</text>
    </view>
  </view>

  <!-- 当前筛选状态 -->
  <view v-if="species" class="qh-filterbar">
    <text class="qh-filterbar__text">{{ species }}</text>
    <text class="qh-filterbar__clear" @click="reset">清除筛选</text>
  </view>

  <text v-else class="qh-sectionlabel">{{ heading }}</text>

  <!-- 告警列表 -->
  <view v-for="item in items" :key="item.id" class="qh-card qh-alarmcard" style="cursor:pointer" @click="emit('open', item)">
    <view class="qh-alarmcard__top">
      <image class="qh-thumb" :src="store.media('captures/' + item.snapshot)" mode="aspectFill"/>
      <view class="qh-alarmcard__mid">
        <view class="qh-alarmcard__titlerow">
          <text class="qh-alarmcard__title">{{ item.species }} · {{ item.count }} 只</text>
          <text class="qh-badge" :class="'qh-badge--' + item.status">{{ statusLabel[item.status] }}</text>
        </view>
        <text class="qh-alarmcard__meta">{{ shortTime(item.at) }} · 东区 · 01 号监控点</text>
        <text class="qh-alarmcard__stat">录像 {{ item.video_time.toFixed(1) }} 秒 · 置信度 {{ (item.confidence * 100).toFixed(0) }}%</text>
      </view>
      <text class="qh-chevron">›</text>
    </view>
  </view>

  <!-- 加载更多：分页而非一次渲染全部 -->
  <button v-if="more" class="qh-btn qh-btn--secondary qh-btn--sm" style="width:100%" :disabled="loading" @click="load(true)">
    {{ loading ? '加载中…' : '加载更多告警' }}
  </button>

  <view v-if="!items.length && !loading" style="padding:40px 0;text-align:center">
    <text class="qh-note">{{ species ? '本分类暂无记录' : '当前没有待处理告警' }}</text>
  </view>

  <text v-if="error" class="qh-note" style="display:block">{{ error }}</text>
</template>
