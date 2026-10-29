<script setup lang="ts">
import { onShow, onHide } from '@dcloudio/uni-app'
import { useOrchard } from './store'
const store = useOrchard()
onShow(() => store.resume())
onHide(() => store.suspend())
</script>
<style>
@import './styles.css';
</style>
