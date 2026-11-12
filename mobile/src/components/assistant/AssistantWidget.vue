<script setup lang="ts">
// AI 助手悬浮层(挂 AppHost 根层,主题/页面切换不卸载):
// - 按钮态:首页右缘竖排小按钮(host.page==='monitor' 且未开窗)
// - 小窗态:右下浮窗,■ 最大化 → AppHost 的 assistant 整页 overlay;— 收起回按钮
// - 整页态由 AppHost overlay 承载,本组件此时不渲染窗口
// 层级惯例照抄 .qh-mask:fixed 居中 390px(max-width:100%);容器 pointer-events:none 穿透,
// 交互元素显式 auto;小窗本体 auto 接管点击,窗外空白区域仍可点到底层页面。
import { computed } from 'vue'
import { useHost } from '../host/hostContext'
import AssistantChat from './AssistantChat.vue'

const host = useHost()
const showTab = computed(() => host.page === 'monitor' && !host.assistantOpen && !host.assistantMax)
const showWin = computed(() => host.assistantOpen && !host.assistantMax)
</script>

<template>
  <view class="as-layer">
    <!-- 按钮态:首页侧边栏小按钮 -->
    <view v-if="showTab" class="as-tab" @click="host.assistantOpen = true">
      <svg width="14" height="14" viewBox="0 0 20 20" fill="none"><path d="M10 2l1.8 4.9L17 8.7l-4.2 3 1 5.3L10 14.4l-3.8 2.6 1-5.3-4.2-3 5.2-1.8L10 2z" fill="currentColor"/></svg>
      <text class="as-tab__t">AI助手</text>
    </view>

    <!-- 小窗态 -->
    <view v-if="showWin" class="as-win">
      <view class="qh-window as-win__frame">
        <view class="qh-tbar as-win__bar">
          <text class="qh-tbar__t">AI 助手</text>
          <view class="as-win__btns">
            <view class="as-wbtn" aria-label="最大化" @click="host.assistantOpen = false; host.assistantMax = true">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><rect x="1" y="1" width="8" height="8" stroke="currentColor" stroke-width="1.5"/></svg>
            </view>
            <view class="as-wbtn" aria-label="收起" @click="host.assistantOpen = false">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M1 5h8" stroke="currentColor" stroke-width="1.5"/></svg>
            </view>
          </view>
        </view>
        <view class="as-win__body"><AssistantChat /></view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.as-layer{position:fixed;top:0;right:0;bottom:0;left:0;width:390px;max-width:100%;margin:0 auto;pointer-events:none;z-index:15}
/* 按钮态:右缘竖排,避开状态栏与 dock */
.as-tab{pointer-events:auto;position:absolute;right:0;top:calc(var(--statusbar-height) + 120px);display:flex;flex-direction:column;align-items:center;gap:4px;padding:8px 4px;border:2px solid var(--ink-900);border-right:0;background:var(--accent);color:var(--accent-fg);box-shadow:-3px 3px 0 var(--shadow-ink);cursor:pointer}
.as-tab__t{writing-mode:vertical-rl;font-size:var(--text-2xs);font-weight:700;letter-spacing:2px}
/* signal 主题首页右上是待处理等级表,按钮下移到空档处 */
:global([data-theme='signal']) .as-tab{top:calc(var(--statusbar-height) + 330px)}
/* 小窗态:右下,dock 上方 */
.as-win{pointer-events:auto;position:absolute;right:10px;bottom:calc(var(--tabbar-height) + 10px);width:358px;max-width:calc(100% - 20px);height:62%;max-height:calc(100% - var(--statusbar-height) - var(--tabbar-height) - 20px);display:flex}
.as-win__frame{width:100%;height:100%;display:flex;flex-direction:column;padding:0}
.as-win__bar{position:relative;flex-shrink:0}
.as-win__btns{position:absolute;right:6px;top:50%;transform:translateY(-50%);display:flex;gap:6px}
.as-wbtn{pointer-events:auto;width:22px;height:18px;border:2px solid var(--ink-900);background:var(--surface-card);color:var(--ink-900);display:flex;align-items:center;justify-content:center;cursor:pointer}
.as-win__body{flex:1 1 0%;min-height:0;padding:8px 10px 10px;display:flex}
.as-win__body > :deep(.as-chat){flex:1;min-width:0}
</style>
