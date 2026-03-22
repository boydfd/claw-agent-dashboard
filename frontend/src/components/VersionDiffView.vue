<template>
  <div class="version-diff-view">
    <div class="diff-table">
      <div v-for="(line, idx) in diffLines" :key="idx"
           class="diff-line" :class="'diff-' + line.type">
        <span class="line-num old-num">{{ line.oldNum ?? '' }}</span>
        <span class="line-num new-num">{{ line.newNum ?? '' }}</span>
        <span class="line-prefix">{{ line.prefix }}</span>
        <span class="line-text">{{ line.text }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  diffLines: { type: Array, required: true }
})
</script>

<style scoped>
.version-diff-view {
  height: 100%;
  overflow: auto;
  background: var(--bg-primary, #0d1117);
}
.diff-table {
  font-family: Menlo, Monaco, 'Courier New', monospace;
  font-size: 12px;
  line-height: 20px;
  min-width: 100%;
}
.diff-line {
  display: flex;
  white-space: pre;
}
.diff-add {
  background: rgba(46, 160, 67, 0.15);
}
.diff-del {
  background: rgba(248, 81, 73, 0.15);
}
.diff-context {
  background: transparent;
}
.line-num {
  width: 40px;
  min-width: 40px;
  text-align: right;
  padding-right: 8px;
  color: rgba(255, 255, 255, 0.3);
  user-select: none;
}
.line-prefix {
  width: 16px;
  min-width: 16px;
  text-align: center;
  color: rgba(255, 255, 255, 0.5);
  user-select: none;
}
.line-text {
  flex: 1;
  padding-right: 16px;
  color: rgba(255, 255, 255, 0.85);
}
</style>
