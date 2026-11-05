<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useOrchard } from '../store'
import type { Alarm } from '../types'
const emit = defineEmits<{ open:[alarm:Alarm] }>()
const store = useOrchard()
const mode = ref('pending'), species = ref(''), items = ref<Alarm[]>([]), groups = ref<{species:string;total:number;pending:number}[]>([])
const error = ref(''), more = ref(false), loading = ref(false)
let version = 0
const heading = computed(() => species.value || (mode.value==='pending' ? '全部待处理' : '按鸟类分类'))
async function load(append=false) {
  const current = ++version; loading.value = true; error.value = ''
  try {
    const query = new URLSearchParams()
    if (mode.value==='pending') query.set('pending','true')
    if (species.value) query.set('species',species.value)
    if (append && items.value.length) query.set('before',String(items.value[items.value.length-1].at))
    const [alarms, index] = await Promise.all([store.request<{items:Alarm[]}>('/alarm-list?'+query),store.request<{alarm_groups:typeof groups.value}>('/library')])
    if (current !== version) return
    items.value = append ? [...items.value,...alarms.items] : alarms.items
    groups.value = index.alarm_groups; more.value = alarms.items.length===100
  } catch(e) { error.value=(e as Error).message } finally { if (current===version) loading.value=false }
}
watch([mode,species,()=>store.state?.counts.pending,()=>store.state?.counts.total], () => { void load() })
onMounted(() => { void load() })
</script>
<template>
  <text class="title">告警中心</text><text class="subtitle">先处理待办，再按鸟类查阅</text>
  <view class="tabs"><button :class="{selected:mode==='pending'}" @click="mode='pending';species=''">全部待处理 · {{ store.state?.counts.pending }}</button><button :class="{selected:mode==='species'}" @click="mode='species';species=''">按鸟类分类</button></view>
  <template v-if="mode==='species' && !species">
    <view v-for="group in groups" :key="group.species" class="species-folder" @click="species=group.species"><text class="folder-symbol">▱</text><view class="grow"><text class="card-title">{{ group.species }}</text><text class="small">{{ group.total }} 条告警 · {{ group.pending }} 条待处理</text></view><text>›</text></view>
    <view v-if="!groups.length" class="empty"><text>检测到鸟类后，会在这里自动分类</text></view>
  </template>
  <template v-else>
    <view class="section-heading"><text>{{ heading }}</text><button v-if="species" class="text-button" @click="species=''">返回鸟类目录</button></view>
    <view v-for="item in items" :key="item.id" class="list-card" @click="emit('open',item)"><view class="row"><image class="thumb" :src="store.media('captures/'+item.snapshot)" mode="aspectFill"/><view class="grow"><text class="card-title">{{ item.species }} · {{ item.count }} 只</text><text class="small">{{ new Date(item.at*1000).toLocaleString('zh-CN') }}</text></view><text class="badge" :class="item.status">{{ ({new:'待处理',processing:'执行中',handled:'已处理',ignored:'已忽略'} as Record<string,string>)[item.status] }}</text></view><view class="card-footer"><text>录像 {{ item.video_time.toFixed(1) }} 秒 · 置信度 {{ (item.confidence*100).toFixed(0) }}%</text><text>查看 ›</text></view></view>
    <view v-if="!items.length && !loading" class="empty"><text>{{ mode==='pending'?'当前没有待处理告警':'本分类暂无记录' }}</text></view>
    <button v-if="more" class="secondary full" :disabled="loading" @click="load(true)">加载更多告警</button>
  </template>
  <text v-if="error" class="note">{{ error }}</text>
</template>
