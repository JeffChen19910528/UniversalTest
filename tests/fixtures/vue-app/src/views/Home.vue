<template>
  <form @submit.prevent="submit">
    <input v-model="name" />
    <button type="submit">Send</button>
  </form>
</template>

<script setup>
import { ref } from "vue";

const name = ref("");

async function submit() {
  await fetch("/api/greet", { method: "POST", body: JSON.stringify({ name: name.value }) });
}
</script>
