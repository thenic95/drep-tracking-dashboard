<template>
  <div class="space-y-6">
    <div>
      <h1 class="page-title">Manage DReps</h1>
      <p class="text-gray-500">Add or remove DReps from your tracking list</p>
    </div>

    <DRepManagement @drep-list-changed="onDrepListChanged" />
  </div>
</template>

<script setup>
import DRepManagement from '@/components/DRepManagement.vue'

const onDrepListChanged = () => {
  console.log('DRep list updated')
}
</script>
