<script setup lang="ts">
// AI 助手聊天体:小窗与整页共用,自身不持有会话状态(消息/草稿/流式状态全在 data/assistantStore),
// 组件重挂载(三态切换)零状态损失;滚动位置重挂后归底属于可接受行为。
import { nextTick, onMounted, ref, watch } from 'vue'
import { useHost } from '../host/hostContext'
import { useOrchard } from '../../store'
import { askAssistant, assistantState, checkAssistant, stopAssistant } from '../../data/assistantStore'
import type { AssistantRef } from '../../types'

const host = useHost()
const store = useOrchard()
const listRef = ref<{ $el?: HTMLElement } | null>(null)

const QUICK = ['八哥怎么防？', '最近什么鸟最多？', '红嘴蓝鹊是什么鸟？']

function conn() {
  return { server: store.server, token: store.token }
}
function scrollBottom() {
  void nextTick(() => {
    const el = (listRef.value?.$el || listRef.value) as HTMLElement | undefined
    if (el) el.scrollTop = el.scrollHeight
  })
}
onMounted(() => {
  if (assistantState.configured === null) void checkAssistant(conn())
  scrollBottom()
})
// 流式增量/新消息都触发归底
watch(() => assistantState.msgs.map(m => m.text.length).join(','), scrollBottom)

function send(text?: string) {
  const q = (text ?? assistantState.draft).trim()
  if (!q || assistantState.busy || assistantState.configured === false) return
  void askAssistant(q, conn())
}
function refClick(r: AssistantRef) {
  if (r.kind === 'species' && r.name) host.viewSpeciesGuide(r.name)
  else if (r.kind === 'stats') host.nav('analytics')
}
</script>

<template>
  <view class="as-chat">
    <view v-if="assistantState.configured === false" class="as-chat__guide">
      未配置 DeepSeek Key：在服务端 .runtime/local.json 增加 "deepseek_key": "sk-..." 后重启即可启用
    </view>

    <scroll-view scroll-y class="as-chat__list" ref="listRef">
      <view v-if="!assistantState.msgs.length" class="as-chat__empty">
        <text class="as-chat__empty-t">我是青禾果园 AI 助手</text>
        <text class="as-chat__empty-s">园内 13 种鸟的科普与本园鸟情优先作答，其他问题走通用知识</text>
        <view class="as-chat__chips">
          <view v-for="q in QUICK" :key="q" class="as-chip" @click="send(q)">{{ q }}</view>
        </view>
      </view>
      <view v-for="(m, i) in assistantState.msgs" :key="i" class="as-msg" :class="'as-msg--' + m.role">
        <view class="as-bubble" :class="{ 'as-bubble--err': m.error }">
          <text class="as-bubble__t" :user-select="true">{{ m.text }}<text v-if="m.streaming" class="as-cursor">▍</text></text>
          <view v-if="m.role === 'assistant' && !m.streaming && m.text" class="as-refs">
            <view v-for="(r, j) in m.refs || []" :key="j" class="as-chip as-chip--ref" @click="refClick(r)">
              {{ r.kind === 'stats' ? '参考资料 · 本园统计' : '参考资料 · 知识卡 ' + (r.name || '') }}
            </view>
            <text v-if="!m.refs?.length && !m.error" class="as-refs__generic">AI 通用回答 · 未引用本园知识库</text>
            <text v-if="m.stopped" class="as-refs__generic">已停止</text>
          </view>
        </view>
      </view>
    </scroll-view>

    <view class="as-chat__composer">
      <view class="qh-input as-chat__field">
        <input v-model="assistantState.draft" type="text" placeholder="问点什么，如：八哥怎么防？" confirm-type="send" :disabled="assistantState.configured === false" @confirm="send()"/>
      </view>
      <view v-if="!assistantState.busy" class="as-send" :class="{ 'as-send--off': assistantState.configured === false || !assistantState.draft.trim() }" @click="send()">发送</view>
      <view v-else class="as-send as-send--stop" @click="stopAssistant()">停止</view>
    </view>
    <text class="as-chat__note">科普参考 · AI 不直接操作驱鸟设备</text>
  </view>
</template>

<style scoped>
.as-chat{display:flex;flex-direction:column;height:100%;min-height:0}
.as-chat__guide{border:2px dashed var(--warn-fg);background:var(--warn-bg);color:var(--warn-fg);font-size:var(--text-2xs);padding:6px 8px;line-height:var(--leading-snug);margin-bottom:8px}
.as-chat__list{flex:1 1 0%;min-height:0;overflow-y:auto}
.as-chat__empty{border:2px dashed var(--line-soft);padding:16px 10px;text-align:center;margin-top:6px}
.as-chat__empty-t{display:block;font-size:var(--text-md);font-weight:700;color:var(--ink-900)}
.as-chat__empty-s{display:block;font-size:var(--text-2xs);color:var(--ink-400);margin-top:4px;line-height:var(--leading-snug)}
.as-chat__chips{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:10px}
.as-chip{border:2px solid var(--ink-900);background:var(--surface-card);font-size:var(--text-2xs);font-weight:700;padding:3px 8px;cursor:pointer}
.as-chip--ref{border-color:var(--accent);color:var(--accent);font-size:var(--text-2xs)}
.as-msg{display:flex;margin-top:8px}
.as-msg--user{justify-content:flex-end}
.as-msg--assistant{justify-content:flex-start}
.as-bubble{max-width:86%;border:2px solid var(--ink-900);padding:6px 9px;box-shadow:2px 2px 0 var(--shadow-ink)}
.as-msg--user .as-bubble{background:var(--ink-900);color:var(--surface-card);box-shadow:none}
.as-msg--assistant .as-bubble{background:var(--surface-card);color:var(--ink-900)}
.as-bubble--err{border-color:var(--danger-fg);color:var(--danger-fg)}
.as-bubble__t{font-size:var(--text-sm);line-height:var(--leading-normal);word-break:break-word;white-space:pre-wrap}
.as-cursor{animation:as-blink 1s steps(2) infinite;color:var(--accent)}
@keyframes as-blink{50%{opacity:0}}
.as-refs{display:flex;flex-wrap:wrap;gap:5px;align-items:center;margin-top:6px;padding-top:5px;border-top:1px dashed var(--line-soft)}
.as-refs__generic{font-size:var(--text-2xs);color:var(--ink-400)}
.as-chat__composer{display:flex;align-items:center;gap:8px;margin-top:8px}
.as-chat__field{flex:1;min-width:0}
.as-send{border:2px solid var(--ink-900);background:var(--accent);color:var(--accent-fg);font-size:var(--text-sm);font-weight:700;padding:7px 11px;box-shadow:2px 2px 0 var(--shadow-ink);cursor:pointer;white-space:nowrap}
.as-send--off{opacity:.4;cursor:not-allowed}
.as-send--stop{background:var(--warn-bg);color:var(--warn-fg)}
.as-chat__note{display:block;font-size:var(--text-2xs);color:var(--ink-300);text-align:center;margin-top:6px}
</style>
