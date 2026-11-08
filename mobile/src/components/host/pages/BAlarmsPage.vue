<script setup lang="ts">
// B 主题告警页:平移,告警打开走 host.openAlarm
import { useHost } from '../hostContext'
import BirdAlarms from '../../BirdAlarms.vue'

const host = useHost()
</script>

<template>
  <BirdAlarms @open="host.openAlarm" />
</template>
