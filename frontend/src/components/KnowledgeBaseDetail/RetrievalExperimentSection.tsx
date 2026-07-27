import type {
  RagRetrievalPresetPublic,
} from "@/client"

import type {
  KnowledgeBaseEvaluationController,
} from "./useKnowledgeBaseEvaluation"

export function RetrievalExperimentSection({
  evaluation,
}: {
  evaluation:
    KnowledgeBaseEvaluationController
}) {
  const settings =
    evaluation.retrievalSettings
  const setSettings =
    evaluation.setRetrievalSettings
  const presetsQuery =
    evaluation.ragRetrievalPresetsQuery
  const createMutation =
    evaluation.createRagRetrievalPresetMutation
  const deleteMutation =
    evaluation.deleteRagRetrievalPresetMutation

  return (
    <section className="space-y-4 rounded-2xl border border-slate-300 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          RAG 检索参数与实验信息
        </h2>
        <p className="text-sm leading-6 text-slate-600">
          当前参数用于单条评测和批量评测。语义权重与关键词权重同时为 0 时，会自动回退到 0.75 / 0.25。
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <NumberField
          label="top_k"
          min={1}
          max={20}
          value={settings.topK}
          onChange={(value) => {
            setSettings((current) => ({
              ...current,
              topK: value,
            }))
          }}
        />
        <NumberField
          label="semantic_weight"
          min={0}
          max={1}
          step={0.05}
          value={settings.semanticWeight}
          onChange={(value) => {
            setSettings((current) => ({
              ...current,
              semanticWeight: value,
            }))
          }}
        />
        <NumberField
          label="keyword_weight"
          min={0}
          max={1}
          step={0.05}
          value={settings.keywordWeight}
          onChange={(value) => {
            setSettings((current) => ({
              ...current,
              keywordWeight: value,
            }))
          }}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <PresetButton
          label="默认 0.75 / 0.25"
          onClick={() => setSettings({
            topK: 5,
            semanticWeight: 0.75,
            keywordWeight: 0.25,
          })}
        />
        <PresetButton
          label="偏语义 0.9 / 0.1"
          onClick={() => setSettings({
            topK: 5,
            semanticWeight: 0.9,
            keywordWeight: 0.1,
          })}
        />
        <PresetButton
          label="偏关键词 0.6 / 0.4"
          onClick={() => setSettings({
            topK: 5,
            semanticWeight: 0.6,
            keywordWeight: 0.4,
          })}
        />
        <PresetButton
          label="高召回 top_k=8"
          onClick={() => setSettings({
            topK: 8,
            semanticWeight: 0.75,
            keywordWeight: 0.25,
          })}
        />
      </div>

      <div className="rounded-lg border border-sky-100 bg-sky-50 px-3 py-2 text-xs text-sky-700">
        实际参数：top_k = {evaluation.normalizedRetrievalSettings.topK}，semantic_weight = {evaluation.normalizedRetrievalSettings.semanticWeight}，keyword_weight = {evaluation.normalizedRetrievalSettings.keywordWeight}
      </div>

      <div className="grid grid-cols-1 gap-3 border-t border-slate-200 pt-4 md:grid-cols-2">
        <input
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
          placeholder="批量评测名称，可选"
          value={evaluation.evalBatchName}
          onChange={(event) => {
            evaluation.setEvalBatchName(
              event.target.value,
            )
          }}
        />
        <input
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
          placeholder="批量评测备注，可选"
          value={evaluation.evalBatchNote}
          onChange={(event) => {
            evaluation.setEvalBatchNote(
              event.target.value,
            )
          }}
        />
      </div>

      <div className="space-y-3 border-t border-slate-200 pt-4">
        <h3 className="font-medium text-slate-900">
          参数预设
        </h3>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <input
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            placeholder="预设名称"
            value={evaluation.presetName}
            onChange={(event) => {
              evaluation.setPresetName(
                event.target.value,
              )
            }}
          />
          <input
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            placeholder="预设备注，可选"
            value={evaluation.presetNote}
            onChange={(event) => {
              evaluation.setPresetNote(
                event.target.value,
              )
            }}
          />
        </div>

        <button
          type="button"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:text-sky-700 disabled:opacity-50"
          onClick={
            evaluation.handleCreateRagRetrievalPreset
          }
          disabled={createMutation.isPending}
        >
          {createMutation.isPending
            ? "保存中..."
            : "保存当前参数为预设"}
        </button>

        {createMutation.isError || deleteMutation.isError ? (
          <pre className="whitespace-pre-wrap text-sm text-rose-600">
            {JSON.stringify(
              createMutation.error
              ?? deleteMutation.error,
              null,
              2,
            )}
          </pre>
        ) : null}

        {presetsQuery.isLoading ? (
          <div className="text-sm text-slate-600">
            正在加载参数预设...
          </div>
        ) : null}

        {presetsQuery.data ? (
          <div className="space-y-2">
            {presetsQuery.data.data.length === 0 ? (
              <div className="text-sm text-slate-600">
                暂无参数预设。
              </div>
            ) : (
              presetsQuery.data.data.map(
                (preset) => (
                  <PresetRow
                    key={preset.id}
                    preset={preset}
                    onApply={() => {
                      evaluation.handleApplyRagRetrievalPreset(
                        preset,
                      )
                    }}
                    onDelete={() => {
                      evaluation.handleDeleteRagRetrievalPreset(
                        preset.id,
                      )
                    }}
                    deleting={
                      deleteMutation.isPending
                    }
                  />
                ),
              )
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
  min,
  max,
  step,
}: {
  label: string
  value: number
  onChange: (value: number) => void
  min: number
  max: number
  step?: number
}) {
  return (
    <label className="space-y-1">
      <span className="text-sm text-slate-600">
        {label}
      </span>
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
        value={value}
        onChange={(event) => {
          onChange(
            Number(event.target.value),
          )
        }}
      />
    </label>
  )
}

function PresetButton({
  label,
  onClick,
}: {
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 transition hover:border-sky-300 hover:text-sky-700"
      onClick={onClick}
    >
      {label}
    </button>
  )
}

function PresetRow({
  preset,
  onApply,
  onDelete,
  deleting,
}: {
  preset: RagRetrievalPresetPublic
  onApply: () => void
  onDelete: () => void
  deleting: boolean
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-slate-300 bg-slate-50 p-3">
      <div>
        <div className="font-medium text-slate-900">
          {preset.name}
        </div>
        <div className="text-xs text-slate-600">
          top_k={preset.top_k} ｜ S={preset.semantic_weight} ｜ K={preset.keyword_weight}
        </div>
        {preset.note ? (
          <div className="mt-1 text-xs text-slate-600">
            {preset.note}
          </div>
        ) : null}
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          className="rounded border border-slate-300 bg-white px-2 py-1 text-xs"
          onClick={onApply}
        >
          应用
        </button>
        <button
          type="button"
          className="rounded border border-rose-200 bg-white px-2 py-1 text-xs text-rose-600"
          onClick={onDelete}
          disabled={deleting}
        >
          删除
        </button>
      </div>
    </div>
  )
}
