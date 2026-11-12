<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { SPECIES_GUIDE } from '../../data/speciesGuide'
import type { SpeciesKnowledge } from '../../types'
import { useOrchard } from '../../store'
import { useHost } from './hostContext'

const host = useHost()
const store = useOrchard()
const open = ref(false)
const names = ref(SPECIES_GUIDE.map(s => s.name))
const groups = ref<{ species: string; total: number; pending: number }[]>([])
const countsReady = ref(false)
const options = computed(() => {
  const byName = new Map(groups.value.map(g => [g.species, g]))
  return [...new Set([...names.value, ...groups.value.map(g => g.species)])].map(name => ({ name, group: byName.get(name) }))
})
const quick = computed(() => options.value.filter(option => option.group?.total || option.name === host.alarmSpecies))

async function load() {
  const [knowledge, library] = await Promise.allSettled([
    store.request<{ items: SpeciesKnowledge[] }>('/knowledge'),
    store.request<{ alarm_groups: { species: string; total: number; pending: number }[] }>('/library?offset=0'),
  ])
  names.value = knowledge.status === 'fulfilled' && knowledge.value.items.length
    ? knowledge.value.items.map(s => s.name) : SPECIES_GUIDE.map(s => s.name)
  countsReady.value = library.status === 'fulfilled'
  groups.value = library.status === 'fulfilled' ? library.value.alarm_groups || [] : []
}
function pick(name: string) {
  host.alarmSpecies = name
  open.value = false
}
watch(() => host.page, page => { if (page === 'alarms') void load() })
onMounted(() => { if (host.page === 'alarms') void load() })
</script>

<template>
  <view class="species-filter" :class="{ 'is-signal': host.theme === 'signal' }">
    <view class="species-filter__row">
      <button class="species-filter__chip species-filter__all" :class="{ 'is-on': !host.alarmSpecies }" aria-label="展开全部物种筛选" @click="open = true">全部 ▾</button>
      <scroll-view scroll-x class="species-filter__scroll" :show-scrollbar="false">
        <view class="species-filter__chips">
          <text v-for="option in quick" :key="option.name" class="species-filter__chip" :class="{ 'is-on': host.alarmSpecies === option.name }" @click="pick(option.name)">
            {{ option.name }}<text v-if="countsReady && option.group" class="species-filter__count"> {{ option.group.pending }}</text>
          </text>
        </view>
      </scroll-view>
    </view>
    <text class="species-filter__hint">数字为待处理告警数 · 点击“全部”选择任意物种或清除筛选</text>

    <view v-if="open" class="qh-mask qh-mask--bottom is-open" @click.self="open = false">
      <view class="qh-sheet species-filter__sheet">
        <view class="qh-sheet__grab"/>
        <view class="qh-sheet__titlerow">
          <text class="qh-sheet__title">选择物种 · {{ options.length }} 类</text>
          <button class="qh-iconbtn--sm" aria-label="关闭物种选择" @click="open = false">×</button>
        </view>
        <view class="species-filter__grid">
          <button class="species-filter__option" :class="{ 'is-on': !host.alarmSpecies }" @click="pick('')">全部</button>
          <button v-for="option in options" :key="option.name" class="species-filter__option" :class="{ 'is-on': host.alarmSpecies === option.name }" @click="pick(option.name)">
            {{ option.name }}<text v-if="countsReady" class="species-filter__count"> · 待处理 {{ option.group?.pending ?? 0 }}</text>
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.species-filter{margin:4px 14px 6px}
.species-filter__row{display:flex;align-items:stretch;gap:7px;min-width:0}
.species-filter__scroll{flex:1;min-width:0;width:0;white-space:nowrap}
.species-filter__chips{display:inline-flex;gap:7px;padding:4px 0 8px}
.species-filter__chip,.species-filter__option{border:2px solid var(--ink-900);background:var(--surface-card);color:var(--ink-900);font-size:11px;font-weight:700;cursor:pointer;border-radius:0}
.species-filter__chip{display:inline-flex;align-items:center;flex-shrink:0;padding:4px 11px}
.species-filter__all{align-self:flex-start;min-height:30px;margin:4px 0 8px;white-space:nowrap}
.species-filter__chip.is-on,.species-filter__option.is-on{background:var(--ink-900);color:var(--surface-card)}
.species-filter__count{font-size:10px}
.species-filter__hint{display:block;font-size:9px;color:var(--ink-400);margin-top:2px}
.species-filter__sheet{padding-bottom:12px}
.species-filter__grid{display:flex;flex-wrap:wrap;gap:7px;padding:10px 0 2px}
.species-filter__option{padding:7px 9px;text-align:left}
.is-signal .species-filter__chip,.is-signal .species-filter__option{font-weight:900}
.is-signal .species-filter__chip.is-on,.is-signal .species-filter__option.is-on{color:#f5c400}
</style>
