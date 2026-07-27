type KnowledgeBaseDetailPageStateProps = {
  title: string
  description?: string
  tone?: "neutral" | "error"
}

export function KnowledgeBaseDetailPageState({
  title,
  description,
  tone = "neutral",
}: KnowledgeBaseDetailPageStateProps) {
  const toneClassName =
    tone === "error"
      ? "border-rose-200 bg-rose-50 text-rose-800"
      : "border-slate-200 bg-white text-slate-700"

  return (
    <main className="min-h-screen bg-slate-50/70 px-4 py-8 md:px-6">
      <section
        className={`mx-auto max-w-3xl rounded-2xl border p-6 shadow-sm ${toneClassName}`}
        role={
          tone === "error"
            ? "alert"
            : "status"
        }
      >
        <h1 className="text-lg font-semibold">
          {title}
        </h1>

        {description ? (
          <p className="mt-2 text-sm leading-6 opacity-90">
            {description}
          </p>
        ) : null}
      </section>
    </main>
  )
}
