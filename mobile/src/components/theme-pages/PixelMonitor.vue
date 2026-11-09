<script setup lang="ts">
// 像素果园监控主页 —— 1:1 复刻 docs/ui-y/d-pixel.html(真实数据 + 语义事件)
// 口径:鸟精灵=事件装饰(不表示在场鸟);HUD 显示当日日期;PIP=最近抓拍(标注时间);
//       图鉴=最近实际抓拍;无待处理告警时对话框显示"果园平静"且无驱离/忽略按钮。
import { computed, onMounted, ref } from 'vue'
import { useHost, shortTime, type RepelMode } from '../host/hostContext'
import { useWorkspace } from '../host/useWorkspace'
import { useOrchard } from '../../store'
import type { Stats } from '../../types'

const host = useHost()
const store = useOrchard()
const ws = useWorkspace(store)

const stats = ref<Stats | null>(null)
const wsOpen = ref(false)
const menuOpen = ref(true)
const today = computed(() => {
  const d = new Date()
  return `${d.getMonth() + 1}月${d.getDate()}日`
})
const todayAlarms = computed(() => stats.value ? stats.value.breakdown.new + stats.value.breakdown.processing + stats.value.breakdown.handled + stats.value.breakdown.ignored : 0)
const birdCount = computed(() => Math.min(3, todayAlarms.value)) // 事件装饰,非在场鸟
const latest = computed(() => host.pending[0] || null)
const recent = computed(() => (host.s?.alarms || []).slice(0, 3))
const modeName = computed(() => ({ acoustic: '声波驱离', infrared: '红外驱离', both: '双模驱离' } as Record<string, string>)[host.mode] || '双模驱离')
const canRepel = computed(() => !!latest.value && !host.store.busy && !host.offline && !host.store.active)

async function loadStats() { try { stats.value = await store.request<Stats>('/stats?range=today') } catch { /* HUD 显示 0 */ } }
onMounted(loadStats)

function requestRepel() {
  if (!canRepel.value) return
  host.selectedAlarm = latest.value!.id
  host.modal = 'mConfirm' // 道具使用同样经人工确认弹窗
}
function requestIgnore() {
  if (!latest.value) return
  void host.run(() => host.requestIgnore(latest.value!.id))
}
const shotUrl = (snap: string) => store.media('captures/' + snap)
</script>

<template>
  <!-- 像素场景 -->
  <view class="px-scene">
    <view class="px-sky"><i class="b1"/><i class="b2"/><i class="b3"/><i class="b4"/><view class="px-cloud c1"/><view class="px-cloud c2"/></view>
    <view class="px-hill"/>
    <view class="px-field">
      <view class="px-shadow"/>
      <view class="px-tree" style="left:18px;top:8px"><view class="leaf2"/><view class="crown"/><view class="trunk"/></view>
      <view class="px-tree" style="left:150px;top:4px"><view class="leaf2"/><view class="crown"/><view class="trunk"/></view>
      <view class="px-tree" style="left:288px;top:10px"><view class="leaf2"/><view class="crown"/><view class="trunk"/></view>
      <view class="px-tree" style="left:82px;top:120px"><view class="leaf2"/><view class="crown"/><view class="trunk"/></view>
      <view class="px-tree" style="left:246px;top:128px"><view class="leaf2"/><view class="crown"/><view class="trunk"/></view>
      <!-- 鸟精灵:今日告警事件装饰(min(3, 今日告警),不代表在场鸟) -->
      <view v-for="n in birdCount" :key="n" class="px-bird" :class="'b' + n"/>
      <view class="px-pond"/>
    </view>
    <view class="px-grass2"/>
    <view class="px-fence"><view class="rail r1"/><view class="rail r2"/><view class="post" v-for="n in 5" :key="n" :style="{ left: (14 + (n - 1) * 76) + 'px' }"/></view>
    <view class="px-grass"/>

    <!-- HUD -->
    <view class="px-hud">
      <view class="px-chip"><text class="day">{{ today }}</text><text>守护中</text></view>
      <view class="px-chip cam" style="cursor:pointer" @click="wsOpen = !wsOpen"><text class="rec"/>CAM-01 · 2FPS</view>
    <view class="px-chip" style="cursor:pointer" @click="host.openScene"><text style="color:#8fe08f">3D 沙盘</text></view>
      <view class="px-chip"><text class="pending mono">{{ host.s?.counts.pending || 0 }}</text><text>待处理</text></view>
    </view>

    <!-- PIP 最近抓拍(非实时画面) -->
    <view class="px-pip" style="cursor:pointer" @click="recent[0] && host.openAlarm(recent[0])">
      <image v-if="recent[0]" :src="shotUrl(recent[0].snapshot)" mode="aspectFill"/>
      <text v-else class="pip-empty mono">NO SHOT</text>
      <text class="pip-tag">{{ recent[0] ? `最近抓拍 · ${recent[0].species} · ${shortTime(recent[0].at)}` : '暂无抓拍' }}</text>
    </view>
  </view>

  <!-- NES 对话框:最新待处理告警 -->
  <view class="px-dialog">
    <view class="px-dlg-who mono">{{ latest ? `告警 No.${latest.id.slice(-4)} · ${shortTime(latest.at)}` : '果园观测' }}</view>
    <template v-if="latest">
      <text class="px-dlg-text">野生的<text class="hl">{{ latest.species }} ×{{ latest.count }}</text> 出现在东南果树区!<text class="hl">{{ Math.round(latest.confidence * 100) }}%</text> 置信度 · 已录像。</text>
      <view class="px-dlg-choices">
        <view class="choice go" style="cursor:pointer" @click="requestRepel">▶ {{ modeName }}</view>
        <view class="choice" style="cursor:pointer" @click="requestIgnore">忽略</view>
      </view>
    </template>
    <text v-else class="px-dlg-text">果园平静…暂无待处理告警。<text class="hl">开始观测</text>后,告警会在这里出现。</text>
    <span class="px-dlg-arrow">▼</span>
  </view>

  <!-- 道具菜单:可收缩小弹窗(右上角锚定,展开/收起均不遮挡) -->
  <view class="px-menu" :class="{ open: menuOpen }">
    <view class="px-menu-hd" style="cursor:pointer" @click="menuOpen = !menuOpen">
      <text>驱离道具</text>
      <text class="px-menu-arrow">{{ menuOpen ? '▾' : '▸' }}</text>
    </view>
    <template v-if="menuOpen">
      <view v-for="m in [{ id: 'acoustic', n: '声波喇叭' }, { id: 'infrared', n: '红外脉冲' }, { id: 'both', n: '双模联动' }]" :key="m.id" class="px-mi" :class="{ on: host.mode === m.id }" style="cursor:pointer" @click="host.mode = m.id as RepelMode">
        <text class="cur">{{ host.mode === m.id ? '▶' : '' }}</text>{{ m.n }}
      </view>
      <view class="px-durs">
        <text v-for="d in [3,5,8]" :key="d" class="px-dur" :class="{ on: host.duration === d }" @click="host.duration = d">{{ d }}s</text>
      </view>
    </template>
  </view>

  <!-- 观测工作区(NES 对话框式,点 CAM 展开) -->
  <view v-if="wsOpen" class="px-dialog px-ws">
    <view class="px-dlg-who mono">观测工作区 · CAM-01</view>
    <VideoPlayer v-if="ws.path.value" :path="ws.path.value" :autoplay="ws.running.value" />
    <text v-else class="px-dlg-text">{{ ws.selected.value?.name || '服务器演示录像' }} — 导入视频后开始观测。</text>
    <view class="px-dlg-choices">
      <view class="choice go" style="cursor:pointer" @click="ws.running.value ? ws.stop() : ws.start()">{{ ws.running.value ? '■ 停止观测' : '▶ 开始观测' }}</view>
      <view class="choice" style="cursor:pointer" @click="ws.choose">导入视频</view>
    </view>
    <view v-if="ws.uploading.value || ws.running.value" class="px-ws-prog">
      <text class="mono">{{ ws.uploading.value ? `上传 ${ws.percent.value}%` : `分析 ${Math.floor(ws.monitor.value?.progress || 0)}%` }}</text>
      <view class="bar"><view :style="{ width: (ws.uploading.value ? ws.percent.value : ws.monitor.value?.progress || 0) + '%' }"/></view>
    </view>
    <text v-if="ws.error.value" class="px-dlg-text err">{{ ws.error.value }}</text>
    <text v-if="ws.sameVideo.value && ws.monitor.value?.result_ready && ws.monitor.value?.task_id" class="px-dlg-text hl" style="cursor:pointer">
      <a :href="store.media(`media/${ws.monitor.value!.task_id}/result.mp4`)+'&download=true'" style="color:inherit">▼ 下载结果视频</a>
    </text>
    <span class="px-dlg-arrow" style="cursor:pointer" @click="wsOpen = false">▲ 收起</span>
  </view>

  <!-- 图鉴条:最近实际抓拍 -->
  <view class="px-dex">
    <text class="px-dex-lbl">最近抓拍 {{ recent.length }}</text>
    <view v-for="(a, i) in recent" :key="a.id" class="px-dex-slot" style="cursor:pointer" @click="host.openAlarm(a)">
      <image :src="shotUrl(a.snapshot)" mode="aspectFill"/>
    </view>
    <view v-for="n in Math.max(0, 4 - recent.length)" :key="'e' + n" class="px-dex-slot empty"/>
  </view>
</template>

<style scoped>
.px-scene { position:relative; height:430px; overflow:hidden; border:3px solid #10130c; }
/* 色带天空(硬切,非渐变) */
.px-sky { position:absolute; left:0; right:0; top:0; height:120px; }
.px-sky i { position:absolute; left:0; right:0; }
.px-sky .b1 { top:0; height:32px; background:#7cc6de; }
.px-sky .b2 { top:32px; height:30px; background:#8fd3e8; }
.px-sky .b3 { top:62px; height:30px; background:#a3ddf0; }
.px-sky .b4 { top:92px; height:28px; background:#b7e6f5; }
.px-cloud { position:absolute; background:#fff; box-shadow:14px 6px 0 #fff,28px 0 0 #fff; }
.px-cloud.c1 { left:36px; top:26px; width:34px; height:13px; }
.px-cloud.c2 { left:220px; top:52px; width:40px; height:11px; }
.px-hill { position:absolute; left:0; right:0; top:118px; height:22px; background:#a8cf8e; box-shadow:inset 0 -7px 0 #93bf77; }
.px-field { position:absolute; left:0; right:0; top:140px; bottom:110px; background:#6ea24e; }
.px-shadow { position:absolute; left:0; right:0; top:110px; height:9px; background:#5f9142; box-shadow:0 20px 0 #5f9142,0 40px 0 #5f9142; }
/* 树 */
.px-tree { position:absolute; }
.px-tree .crown { position:relative; width:50px; height:28px; background:#3c6129; box-shadow:0 -7px 0 #3c6129,inset 0 -6px 0 #2f4e20; }
.px-tree .leaf2 { position:absolute; left:-6px; top:-12px; width:62px; height:11px; background:#6f9c4a; }
.px-tree .trunk { position:relative; left:19px; width:12px; height:24px; background:#6b4a2f; box-shadow:0 5px 0 #59391f; }
/* 鸟精灵(box-shadow 像素鸟) */
.px-bird { position:absolute; width:18px; height:14px; background:#c9b6a9; box-shadow:-6px 2px 0 #8b8278,3px 6px 0 #a89f96,8px 0 0 0 #c9b6a9,10px 1px 0 #23201c; }
.px-bird.b1 { left:118px; bottom:118px; }
.px-bird.b2 { left:220px; bottom:138px; transform:scale(.8); }
.px-bird.b3 { left:60px; bottom:150px; transform:scale(.7); }
.px-pond { position:absolute; left:132px; bottom:28px; width:92px; height:26px; background:#5fa8d8; box-shadow:inset 0 -6px 0 #4a8cbc,inset 0 4px 0 #7fc0ea; }
.px-grass2 { position:absolute; left:0; right:0; bottom:96px; height:56px; background:#4f8140; }
.px-fence { position:absolute; left:0; right:0; bottom:150px; height:26px; }
.px-fence .rail { position:absolute; left:0; right:0; height:5px; background:#9c7a4e; }
.px-fence .rail.r1 { bottom:15px; } .px-fence .rail.r2 { bottom:5px; }
.px-fence .post { position:absolute; bottom:0; width:9px; height:26px; background:#8a6a44; box-shadow:inset -3px 0 0 #735533; }
.px-grass { position:absolute; left:0; right:0; bottom:0; height:96px; background:#548539; box-shadow:inset 0 9px 0 #63a04b; }
/* HUD */
.px-hud { position:absolute; left:0; right:0; top:0; display:flex; justify-content:space-between; padding:10px; z-index:6; }
.px-chip { background:#191d14; color:#fff; font-size:10px; font-weight:800; letter-spacing:1px; padding:4px 8px; box-shadow:0 3px 0 rgba(0,0,0,.35); display:flex; align-items:center; gap:5px; }
.px-chip .day { color:#f8d94a; }
.px-chip .rec { width:8px; height:8px; background:#e5482e; animation:qhBlink 1.2s steps(2) infinite; }
.px-chip .pending { color:#f8d94a; font-size:12px; }
/* PIP */
.px-pip { position:absolute; right:10px; top:46px; width:118px; height:82px; border:4px solid #191d14; box-shadow:0 3px 0 rgba(0,0,0,.4); z-index:6; background:#10130c; }
.px-pip image, .px-pip uni-image { width:100%; height:100%; object-fit:cover; }
.px-pip .pip-empty { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; color:#7f8a72; font-size:10px; }
.px-pip .pip-tag { position:absolute; left:0; right:0; bottom:0; background:rgba(25,29,20,.85); color:#f8d94a; font-size:8px; font-weight:800; padding:2px 4px; letter-spacing:.5px; }
/* NES 对话框 */
.px-dialog { position:relative; margin:-56px 12px 0; background:#10130c; border:4px solid #f4f1e4; box-shadow:0 0 0 4px #10130c,0 6px 0 rgba(0,0,0,.45); padding:12px 13px; z-index:8; }
.px-dlg-who { color:#f8d94a; font-size:10px; font-weight:800; letter-spacing:2px; margin-bottom:5px; }
.px-dlg-text { color:#f4f1e4; font-size:13px; font-weight:700; line-height:1.7; display:block; }
.px-dlg-text .hl, .px-dlg-text .hl { color:#8fe08f; }
.px-dlg-text.err { color:#e5482e; }
.px-dlg-choices { display:flex; gap:6px; margin-top:9px; }
.px-dlg-choices .choice { flex:1; border:2px solid #f4f1e4; color:#f4f1e4; font-size:11px; font-weight:800; text-align:center; padding:6px 0; }
.px-dlg-choices .choice.go { background:#f4f1e4; color:#10130c; }
.px-dlg-arrow { position:absolute; right:10px; bottom:6px; color:#f4f1e4; font-size:12px; animation:qhBlink 1s steps(2) infinite; }
/* 道具菜单 */
.px-menu { position:absolute; right:10px; top:140px; width:124px; background:#10130c; border:4px solid #f4f1e4; box-shadow:0 0 0 4px #10130c,0 6px 0 rgba(0,0,0,.45); padding:9px 10px; z-index:9; }
.px-menu:not(.open) { width:auto; padding:6px 10px; }
.px-menu:not(.open) .px-menu-hd { border-bottom:0; margin-bottom:0; }
.px-menu-hd { display:flex; justify-content:space-between; align-items:center; gap:8px; color:#f8d94a; font-size:10px; font-weight:800; letter-spacing:2px; border-bottom:2px solid #3a4130; padding-bottom:5px; margin-bottom:7px; }
.px-menu:not(.open) .px-menu-hd { border-bottom-width:1px; padding-bottom:3px; margin-bottom:0; }
.px-menu-arrow { font-size:10px; }
.px-mi { color:#f4f1e4; font-size:11px; font-weight:700; padding:4px 0; display:flex; gap:4px; }
.px-mi .cur { color:#f8d94a; width:12px; }
.px-mi.on { color:#8fe08f; }
.px-durs { display:flex; gap:4px; margin-top:7px; border-top:2px solid #3a4130; padding-top:7px; }
.px-durs .px-dur { flex:1; border:2px solid #f4f1e4; color:#f4f1e4; font-size:10px; font-weight:800; text-align:center; padding:3px 0; }
.px-durs .px-dur.on { background:#f4f1e4; color:#10130c; }
/* 工作区 */
.px-ws { margin-top:10px; }
.px-ws :deep(video), .px-ws :deep(uni-image), .px-ws :deep(image) { width:100%; height:150px; object-fit:cover; }
.px-ws-prog { display:flex; align-items:center; gap:8px; margin-top:8px; color:#f4f1e4; font-size:10px; }
.px-ws-prog .bar { flex:1; height:10px; border:2px solid #f4f1e4; }
.px-ws-prog .bar view { height:100%; background:#8fe08f; }
/* 图鉴 */
.px-dex { display:flex; align-items:center; gap:8px; margin-top:12px; }
.px-dex-lbl { background:#191d14; color:#8fe08f; font-size:9.5px; font-weight:800; letter-spacing:1px; padding:4px 7px; flex-shrink:0; }
.px-dex-slot { width:36px; height:28px; border:3px solid #191d14; overflow:hidden; background:#10130c; flex-shrink:0; }
.px-dex-slot image, .px-dex-slot uni-image { width:100%; height:100%; object-fit:cover; }
.px-dex-slot.empty { background:repeating-conic-gradient(#2c3424 0 25%,#39422e 0 50%) 0 0/6px 6px; }
</style>
