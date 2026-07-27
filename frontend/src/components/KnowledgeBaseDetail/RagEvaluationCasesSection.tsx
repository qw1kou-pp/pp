import type {
  KnowledgeBaseEvaluationController,
} from "./useKnowledgeBaseEvaluation"

export function RagEvaluationCasesSection({
  evaluation,
}: {
  evaluation:
    KnowledgeBaseEvaluationController
}) {
  const query = evaluation.ragEvalCasesQuery
  const createMutation = evaluation.createRagEvalCaseMutation
  const deleteMutation = evaluation.deleteRagEvalCaseMutation
  const seedMutation = evaluation.seedCodeEvalCasesMutation

  return (
    <section className="space-y-5 rounded-2xl border border-slate-300 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          评测样例管理
        </h2>
        <p className="text-sm leading-6 text-slate-600">
          创建固定问题与预期关键词，也可以根据知识库中的代码文件自动生成 Code Eval 样例。
        </p>
      </div>

      <div className="space-y-3 rounded-xl border border-slate-300 bg-slate-50 p-4">
        <h3 className="font-medium text-slate-900">创建评测样例</h3>
        <textarea
          className="min-h-[90px] w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
          placeholder="评测问题"
          value={evaluation.evalQuestion}
          onChange={(event) => evaluation.setEvalQuestion(event.target.value)}
        />
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <input
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            placeholder="预期关键词，逗号或换行分隔"
            value={evaluation.evalKeywords}
            onChange={(event) => evaluation.setEvalKeywords(event.target.value)}
          />
          <input
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            placeholder="预期来源文件，可选"
            value={evaluation.evalSourceFilename}
            onChange={(event) => evaluation.setEvalSourceFilename(event.target.value)}
          />
          <input
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            placeholder="备注，可选"
            value={evaluation.evalNote}
            onChange={(event) => evaluation.setEvalNote(event.target.value)}
          />
        </div>
        <button
          type="button"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium disabled:opacity-50"
          onClick={evaluation.handleCreateRagEvalCase}
          disabled={createMutation.isPending}
        >
          {createMutation.isPending ? "创建中..." : "创建评测样例"}
        </button>
        {createMutation.isError ? (
          <pre className="whitespace-pre-wrap text-sm text-rose-600">
            {JSON.stringify(createMutation.error, null, 2)}
          </pre>
        ) : null}
      </div>

      <div className="space-y-3 rounded-xl border border-slate-300 bg-slate-50 p-4">
        <h3 className="font-medium text-slate-900">生成代码评测集</h3>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <NumberField
            label="最多代码文件数"
            value={evaluation.codeEvalMaxFiles}
            onChange={evaluation.setCodeEvalMaxFiles}
          />
          <NumberField
            label="最多符号数"
            value={evaluation.codeEvalMaxSymbols}
            onChange={evaluation.setCodeEvalMaxSymbols}
          />
        </div>
        <button
          type="button"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium disabled:opacity-50"
          onClick={() => seedMutation.mutate()}
          disabled={seedMutation.isPending}
        >
          {seedMutation.isPending ? "生成中..." : "生成 Code Eval 样例"}
        </button>
        {seedMutation.isError ? (
          <pre className="whitespace-pre-wrap text-sm text-rose-600">
            {JSON.stringify(seedMutation.error, null, 2)}
          </pre>
        ) : null}
      </div>

      <div className="space-y-3">
        <h3 className="font-medium text-slate-900">评测样例列表</h3>
        {query.isLoading ? (
          <div className="text-sm text-slate-600">正在加载评测样例...</div>
        ) : null}
        {query.isError ? (
          <pre className="whitespace-pre-wrap text-sm text-rose-600">
            {JSON.stringify(query.error, null, 2)}
          </pre>
        ) : null}
        {query.data ? (
          <div className="space-y-3">
            <div className="text-sm text-slate-600">
              共 {query.data.count} 条评测样例。
            </div>
            {query.data.data.length === 0 ? (
              <div className="text-sm text-slate-600">暂无评测样例。</div>
            ) : (
              query.data.data.map((item) => {
                const running = evaluation.runningEvalCaseIds.has(item.id)
                const runError = evaluation.evalCaseRunErrors[item.id]

                return (
                  <article
                    key={item.id}
                    className="space-y-3 rounded-xl border border-slate-300 bg-white p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-medium text-slate-900">{item.question}</div>
                        <div className="mt-1 text-xs text-slate-500">
                          关键词：{item.expected_keywords?.join("、") || "-"} ｜ 来源：{item.expected_source_filename || "-"}
                        </div>
                        {item.note ? (
                          <div className="mt-1 text-xs text-slate-500">备注：{item.note}</div>
                        ) : null}
                      </div>

                      <div className="flex gap-2">
                        <button
                          type="button"
                          className="rounded border border-slate-300 bg-white px-2 py-1 text-xs disabled:opacity-50"
                          onClick={() => void evaluation.handleRunRagEvalCase(item.id)}
                          disabled={running}
                        >
                          {running ? "运行中..." : "运行"}
                        </button>
                        <button
                          type="button"
                          className="rounded border border-rose-200 bg-white px-2 py-1 text-xs text-rose-600 disabled:opacity-50"
                          onClick={() => evaluation.handleDeleteRagEvalCase(item.id)}
                          disabled={deleteMutation.isPending}
                        >
                          删除
                        </button>
                      </div>
                    </div>

                    {runError ? (
                      <pre className="whitespace-pre-wrap text-xs text-rose-600">
                        {JSON.stringify(runError, null, 2)}
                      </pre>
                    ) : null}
                  </article>
                )
              })
            )}
          </div>
        ) : null}
      </div>
    </section>
  )
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (value: number) => void
}) {
  return (
    <label className="space-y-1">
      <span className="text-sm text-slate-600">{label}</span>
      <input
        type="number"
        min={1}
        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  )
}
