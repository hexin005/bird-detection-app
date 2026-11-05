<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useOrchard } from '../store'
import VideoPlayer from './VideoPlayer.vue'
type Span = {species:string;start:number;end:number;peak_count:number}
type Archive = {id:string;name:string;status:string;at:number;duration:number;progress:number;result_ready:boolean;stream_ready?:boolean;message:string;species:{species:string;first_seen:number;peak_count:number}[];intervals?:Span[]}
const props = defineProps<{ initialTask?:string; initialTime?:number }>()
const store = useOrchard()
const mode=ref('video'), species=ref(''), items=ref<Archive[]>([]), groups=ref<{species:string;videos:number}[]>([])
const detail=ref<Archive|null>(null), seek=ref(0), error=ref(''), more=ref(false), loading=ref(false)
const original=ref(false)
let timer:ReturnType<typeof setInterval>|null=null, version=0
const path=computed(()=>detail.value && (original.value || detail.value.result_ready || detail.value.stream_ready) ? `media/${detail.value.id}/${original.value?'source':detail.value.result_ready?'result.mp4':'index.m3u8'}`:'')
const labels:Record<string,string>={ended:'已归档',running:'分析中',starting:'准备中',stopped:'已停止',stopping:'正在停止',error:'处理失败',interrupted:'处理中断'}
const badgeOf = (s:string) => 'qh-badge qh-badge--' + ({ended:'handled',running:'running',starting:'info',stopping:'info',stopped:'neutral',error:'failed',interrupted:'new'} as Record<string,string>)[s] || 'qh-badge--neutral'
const shortTime=(v:number)=>new Date(v*1000).toLocaleString('zh-CN',{hour12:false,month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})

async function load(append=false) {
  const current=++version; loading.value=true
  try {
    const data=await store.request<{items:Archive[];species:typeof groups.value}>(`/library?offset=${append?items.value.length:0}${species.value?'&species='+encodeURIComponent(species.value):''}`)
    if(current!==version)return
    items.value=append?[...items.value,...data.items]:data.items; groups.value=data.species; more.value=data.items.length===30; error.value=''
  }catch(e){error.value=(e as Error).message}finally{if(current===version)loading.value=false}
}
async function open(task:string,time=0){try{original.value=false;detail.value=await store.request<Archive>('/library/'+task);seek.value=time}catch(e){error.value=(e as Error).message}}
function folder(value:string){species.value=value;void load()}
onMounted(()=>{void load();if(props.initialTask)void open(props.initialTask,props.initialTime||0);timer=setInterval(()=>{
  if(detail.value && ['starting','running','stopping'].includes(detail.value.status)) {
    const id=detail.value.id
    void store.request<Archive>('/library/'+id).then(value=>{if(detail.value?.id===id)detail.value=value}).catch(()=>{})
  } else if(!detail.value && items.value.length<=30)void load()
},5000)})
onBeforeUnmount(()=>{if(timer)clearInterval(timer);version++})
</script>
<template>
  <view class="qh-subtabs">
    <view class="qh-subtab" :class="{ 'is-active': mode === 'video' }" @click="mode = 'video'; folder('')"><text>按视频</text><view class="qh-subtab__bar"/></view>
    <view class="qh-subtab" :class="{ 'is-active': mode === 'species' }" @click="mode = 'species'; folder('')"><text>按鸟类</text><view class="qh-subtab__bar"/></view>
  </view>

  <template v-if="mode === 'species' && !species">
    <view v-for="group in groups" :key="group.species" class="qh-folder" @click="folder(group.species)">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M4 15c0-5 3.5-9 8.5-9.5 2-.2 3.5.8 3.5 2.3 0 1.2-1 2.2-2.4 2.2h-2.1c-.3 2.8-2.6 5-5.5 5H4z" stroke="#7B9B63" stroke-width="1.5" stroke-linejoin="round"/><path d="M4 15h9.5" stroke="#7B9B63" stroke-width="1.5" stroke-linecap="round"/></svg>
      <view class="qh-folder__info"><text class="qh-folder__name">{{ group.species }}</text><text class="qh-folder__stat">出现在 {{ group.videos }} 次视频检测中</text></view>
      <text class="qh-chevron">›</text>
    </view>
    <text v-if="!groups.length" class="qh-note" style="display:block;padding:30px 0;text-align:center">分析视频后，识别到的鸟类会自动建立分类</text>
  </template>

  <template v-else>
    <text v-if="species" class="qh-sectionlabel">{{ species }} · <text class="qh-linkstrip__cancel" @click="folder('')">返回鸟类目录</text></text>

    <view v-for="item in items" :key="item.id" class="qh-card qh-archcard" style="cursor:pointer" @click="open(item.id, species ? item.species.find(s => s.species === species)?.first_seen || 0 : 0)">
      <view class="qh-archcard__top">
        <view class="qh-archcard__cover"><svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M6 4.5v7l5.5-3.5L6 4.5z" fill="#D3E856"/></svg></view>
        <view class="qh-archcard__info">
          <text class="qh-archcard__name">{{ item.name }}</text>
          <text class="qh-archcard__meta">{{ shortTime(item.at) }} · {{ item.duration.toFixed(1) }} 秒</text>
        </view>
        <text :class="badgeOf(item.status)">{{ labels[item.status] || item.status }}</text>
      </view>
      <view class="qh-chips">
        <text v-for="bird in item.species" :key="bird.species" class="qh-chip">{{ bird.species }}</text>
        <text v-if="!item.species.length" style="font-size:var(--text-2xs);color:var(--ink-300)">{{ item.status === 'ended' ? '未检出鸟类' : '等待识别结果' }}</text>
      </view>
      <view class="qh-archcard__bottom">
        <text class="qh-archcard__saved">{{ item.result_ready ? '结果视频已保存' : `${Math.floor(item.progress || 0)}% · ${item.message}` }}</text>
        <text class="qh-link">回看 ›</text>
      </view>
    </view>

    <view v-if="!items.length && !loading" style="padding:40px 0;text-align:center">
      <text class="qh-note">还没有检测档案，从首页导入视频并开始检测即可自动归档</text>
    </view>
    <button v-if="more" class="qh-btn qh-btn--secondary qh-btn--sm" style="width:100%" :disabled="loading" @click="load(true)">加载更早视频</button>

    <text v-if="mode === 'video' && groups.length" class="qh-sectionlabel">按鸟类视图</text>
    <view v-for="group in (mode === 'video' ? groups.slice(0, 4) : [])" :key="'g-' + group.species" class="qh-folder" @click="mode = 'species'; folder(group.species)">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M4 15c0-5 3.5-9 8.5-9.5 2-.2 3.5.8 3.5 2.3 0 1.2-1 2.2-2.4 2.2h-2.1c-.3 2.8-2.6 5-5.5 5H4z" stroke="#7B9B63" stroke-width="1.5" stroke-linejoin="round"/><path d="M4 15h9.5" stroke="#7B9B63" stroke-width="1.5" stroke-linecap="round"/></svg>
      <view class="qh-folder__info"><text class="qh-folder__name">{{ group.species }}</text><text class="qh-folder__stat">出现在 {{ group.videos }} 次视频检测中</text></view>
      <text class="qh-chevron">›</text>
    </view>
  </template>

  <text v-if="error" class="qh-note" style="display:block">{{ error }}</text>

  <!-- 档案详情 -->
  <view v-if="detail" class="qh-mask qh-mask--bottom is-open" @click.self="detail = null">
    <scroll-view scroll-y class="qh-sheet">
      <view class="qh-sheet__grab"/>
      <view class="qh-sheet__titlerow">
        <view><text class="qh-sheet__title">检测档案</text><text style="display:block;font-size:var(--text-xs);color:var(--ink-400);margin-top:3px">{{ detail.name }}</text></view>
        <view class="qh-iconbtn--sm" @click="detail = null"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2l-8 8" stroke="#6D7F6C" stroke-width="1.5" stroke-linecap="round"/></svg></view>
      </view>

      <view class="qh-seg">
        <view class="qh-seg__item" :class="{ 'is-active': !original }" @click="original = false">检测结果</view>
        <view class="qh-seg__item" :class="{ 'is-active': original }" @click="original = true">原视频对照</view>
      </view>

      <VideoPlayer v-if="path" :path="path" :seek="seek"/>
      <view v-else class="qh-callout" style="padding:12px;border-radius:12px;background:var(--surface-muted);font-size:var(--text-xs);color:var(--ink-500)">{{ detail.message }}；当前还没有可播放片段。</view>

      <view class="qh-btnrow">
        <view v-if="detail.result_ready" class="qh-btn qh-btn--secondary qh-btn--half"><a :href="store.media(`media/${detail.id}/result.mp4`)+'&download=true'" style="color:inherit">下载结果视频 ↓</a></view>
        <view class="qh-btn qh-btn--secondary qh-btn--half"><a :href="store.media(`media/${detail.id}/source`)+'&download=true'" style="color:inherit">下载原视频 ↓</a></view>
      </view>

      <text class="qh-sectionlabel">鸟类出现位置 · 点击跳转</text>
      <view v-for="(span, i) in detail.intervals" :key="i" style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--line-soft)" @click="seek = span.start + Math.random() * 0.0001">
        <text style="font-size:var(--text-base);color:var(--ink-800)">{{ span.species }}</text>
        <text class="qh-tl__time">{{ span.start.toFixed(1) }}–{{ span.end.toFixed(1) }} 秒 · 峰值 {{ span.peak_count }} 只</text>
      </view>
      <text v-if="!detail.intervals?.length" class="qh-note">本次没有检出鸟类，仍可回看完整视频</text>
    </scroll-view>
  </view>
</template>
