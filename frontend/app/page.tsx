import { HealthStatus } from "@/components/health-status";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-6 py-24">
      <h1 className="text-3xl font-semibold tracking-tight">Molecula</h1>
      <p className="text-zinc-600 dark:text-zinc-400">
        Ask about medicines: what they are for, how they work and what they bind to.
      </p>
      <HealthStatus />
    </main>
  );
}
