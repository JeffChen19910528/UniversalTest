import { useState } from "react";

export default function Home() {
  const [name, setName] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    await fetch("/api/greet", { method: "POST", body: JSON.stringify({ name }) });
  }

  return (
    <form onSubmit={submit}>
      <input value={name} onChange={(e) => setName(e.target.value)} />
      <button type="submit">Greet</button>
    </form>
  );
}
