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
const labels:Record<string,string>={ended:'已完成',running:'分析中',starting:'准备中',stopped:'已停止 · 部分结果',stopping:'正在停止',error:'处理失败',interrupted:'处理中断'}
</script>
<template>
  <view class="tabs"><button :class="{selected:mode==='video'}" @click="mode='video';folder('')">按视频</button><button :class="{selected:mode==='species'}" @click="mode='species';folder('')">按鸟类</button></view>
  <template v-if="mode==='species'&&!species">
    <view v-for="group in groups" :key="group.species" class="species-folder" @click="folder(group.species)"><text class="folder-symbol">▱</text><view class="grow"><text class="card-title">{{ group.species }}</text><text class="small">出现在 {{ group.videos }} 次视频检测中</text></view><text>›</text></view>
    <text v-if="!groups.length" class="note">分析视频后，识别到的鸟类会自动建立分类。</text>
  </template>
  <template v-else>
    <view v-if="species" class="section-heading"><text>{{ species }}</text><button class="text-button" @click="folder('')">返回鸟类目录</button></view>
    <view v-for="item in items" :key="item.id" class="video-archive" @click="open(item.id,species?item.species.find(s=>s.species===species)?.first_seen||0:0)"><view class="row"><view class="grow"><text class="card-title">{{ item.name }}</text><text class="small">{{ new Date(item.at*1000).toLocaleString('zh-CN') }} · {{ item.duration.toFixed(1) }} 秒</text></view><text class="badge" :class="item.status">{{ labels[item.status] || item.status }}</text></view><view class="bird-chips"><text v-for="bird in item.species" :key="bird.species">{{ bird.species }}</text><text v-if="!item.species.length">{{ item.status==='ended'?'未检出鸟类':'等待识别结果' }}</text></view><view class="card-footer"><text>{{ item.result_ready?'结果视频已保存':`${Math.floor(item.progress||0)}% · ${item.message}` }}</text><text>回看 ›</text></view></view>
    <view v-if="!items.length&&!loading" class="empty"><text>还没有检测档案</text><text class="small">从首页导入视频并开始检测即可自动归档。</text></view>
    <button v-if="more" class="secondary full" :disabled="loading" @click="load(true)">加载更早视频</button>
  </template>
  <text v-if="error" class="note">{{ error }}</text>
  <view v-if="detail" class="overlay" @click.self="detail=null"><scroll-view scroll-y class="sheet"><view class="sheet-head"><text class="card-title">检测档案</text><button class="icon-button" @click="detail=null">×</button></view><text class="card-title">{{ detail.name }}</text><text class="subtitle">{{ labels[detail.status] }} · {{ detail.duration.toFixed(1) }} 秒</text><view class="tabs"><button :class="{selected:!original}" @click="original=false">检测结果</button><button :class="{selected:original}" @click="original=true">原视频对照</button></view><VideoPlayer v-if="path" :path="path" :seek="seek"/><view v-else class="callout">{{ detail.message }}；当前还没有可播放片段。</view><a v-if="detail.result_ready" class="download-link" :href="store.media(`media/${detail.id}/result.mp4`)+'&download=true'">下载带框结果视频 ↓</a><a class="download-link" :href="store.media(`media/${detail.id}/source`)+'&download=true'">下载原视频 ↓</a><text class="note">模型采样识别，框在采样之间保留。时间段表示检出位置，峰值数量为单帧数量。</text><view class="section-heading"><text>鸟类出现位置 · 点击跳转</text></view><view v-for="(span,i) in detail.intervals" :key="i" class="interval-row" @click="seek=span.start+Math.random()*0.0001"><text>{{ span.species }}</text><text>{{ span.start.toFixed(1) }}–{{ span.end.toFixed(1) }} 秒 · 峰值 {{ span.peak_count }} 只 ›</text></view><text v-if="!detail.intervals?.length" class="note">本次没有检出鸟类，仍可回看完整视频。</text></scroll-view></view>
</template>
