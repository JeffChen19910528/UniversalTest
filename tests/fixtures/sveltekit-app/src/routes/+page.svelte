<script>
  let name = "";

  async function submit() {
    await fetch("/api/greet", { method: "POST", body: JSON.stringify({ name }) });
  }
</script>

<form on:submit|preventDefault={submit}>
  <input bind:value={name} />
</form>
