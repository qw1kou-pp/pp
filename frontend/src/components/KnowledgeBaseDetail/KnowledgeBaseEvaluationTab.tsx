import type {
  KnowledgeBasePublic,
} from "@/client"

import {
  AgentParamTuningSection,
} from "./AgentParamTuningSection"
import {
  AgentSettingsSection,
} from "./AgentSettingsSection"
import {
  CodeEvalAnalysisSection,
} from "./CodeEvalAnalysisSection"
import {
  EvaluationSummarySection,
} from "./EvaluationSummarySection"
import {
  OptimizationExperimentSection,
} from "./OptimizationExperimentSection"
import {
  RagAgentBatchCompareSection,
} from "./RagAgentBatchCompareSection"
import {
  RagAgentCompareDetailSection,
} from "./RagAgentCompareDetailSection"
import {
  RagAgentCompareHistorySection,
} from "./RagAgentCompareHistorySection"
import {
  RagAgentFailureAnalysisSection,
} from "./RagAgentFailureAnalysisSection"
import {
  RagEvaluationCasesSection,
} from "./RagEvaluationCasesSection"
import {
  RagEvaluationRecordsSection,
} from "./RagEvaluationRecordsSection"
import {
  RagEvaluationRunsSection,
} from "./RagEvaluationRunsSection"
import {
  RetrievalExperimentSection,
} from "./RetrievalExperimentSection"
import {
  useKnowledgeBaseEvaluation,
} from "./useKnowledgeBaseEvaluation"

export type KnowledgeBaseEvaluationTabProps = {
  knowledgeBaseId: string
  knowledgeBase: KnowledgeBasePublic
}

export function KnowledgeBaseEvaluationTab({
  knowledgeBaseId,
  knowledgeBase,
}: KnowledgeBaseEvaluationTabProps) {
  const evaluation =
    useKnowledgeBaseEvaluation({
      knowledgeBaseId,
      knowledgeBase,
    })

  return (
    <div className="space-y-6">
      <RagAgentBatchCompareSection
        evaluation={evaluation}
      />

      <RagAgentCompareHistorySection
        isOpen={
          evaluation.compareHistoryOpen
        }
        onToggle={() => {
          evaluation.setCompareHistoryOpen(
            (current) => !current,
          )
        }}
        batchesData={
          evaluation
            .ragAgentCompareBatchesQuery
            .data
        }
        isLoading={
          evaluation
            .ragAgentCompareBatchesQuery
            .isLoading
        }
        isError={
          evaluation
            .ragAgentCompareBatchesQuery
            .isError
        }
        error={
          evaluation
            .ragAgentCompareBatchesQuery
            .error
        }
        selectedCompareBatchId={
          evaluation
            .selectedCompareBatchId
        }
        onSelectBatch={
          evaluation.selectCompareBatch
        }
        onExportMarkdown={(batchId) => {
          evaluation
            .exportRagAgentCompareReportMutation
            .mutate(batchId)
        }}
        onExportDocx={(batchId) => {
          evaluation
            .exportRagAgentCompareDocxReportMutation
            .mutate(batchId)
        }}
        onExportPdf={(batchId) => {
          evaluation
            .exportRagAgentComparePdfReportMutation
            .mutate(batchId)
        }}
        onDeleteBatch={(batchId) => {
          evaluation
            .deleteRagAgentCompareBatchMutation
            .mutate(batchId)
        }}
        isExportMarkdownPending={
          evaluation
            .exportRagAgentCompareReportMutation
            .isPending
        }
        isExportDocxPending={
          evaluation
            .exportRagAgentCompareDocxReportMutation
            .isPending
        }
        isExportPdfPending={
          evaluation
            .exportRagAgentComparePdfReportMutation
            .isPending
        }
        isDeletePending={
          evaluation
            .deleteRagAgentCompareBatchMutation
            .isPending
        }
        exportMarkdownError={
          evaluation
            .exportRagAgentCompareReportMutation
            .error
        }
        exportDocxError={
          evaluation
            .exportRagAgentCompareDocxReportMutation
            .error
        }
        exportPdfError={
          evaluation
            .exportRagAgentComparePdfReportMutation
            .error
        }
        isExportMarkdownError={
          evaluation
            .exportRagAgentCompareReportMutation
            .isError
        }
        isExportDocxError={
          evaluation
            .exportRagAgentCompareDocxReportMutation
            .isError
        }
        isExportPdfError={
          evaluation
            .exportRagAgentComparePdfReportMutation
            .isError
        }
      />

      <RagAgentCompareDetailSection
        isOpen={
          evaluation.compareHistoryOpen
        }
        selectedCompareBatchId={
          evaluation
            .selectedCompareBatchId
        }
        batchDetailData={
          evaluation
            .ragAgentCompareBatchDetailQuery
            .data
        }
        isLoading={
          evaluation
            .ragAgentCompareBatchDetailQuery
            .isLoading
        }
        isError={
          evaluation
            .ragAgentCompareBatchDetailQuery
            .isError
        }
        error={
          evaluation
            .ragAgentCompareBatchDetailQuery
            .error
        }
        onClose={() => {
          evaluation.setSelectedCompareBatchId(
            null,
          )
        }}
      />

      <RagAgentFailureAnalysisSection
        isOpen={
          evaluation.compareHistoryOpen
        }
        batchDetailData={
          evaluation
            .ragAgentCompareBatchDetailQuery
            .data
        }
      />

      <AgentSettingsSection
        evaluation={evaluation}
      />

      <AgentParamTuningSection
        isOpen={
          evaluation
            .agentParamTuningOpen
        }
        onToggle={() => {
          evaluation.setAgentParamTuningOpen(
            (current) => !current,
          )
        }}
        config={
          evaluation.agentParamConfig
        }
        onConfigChange={
          evaluation.setAgentParamConfig
        }
        onRunTuning={() => {
          evaluation
            .runAgentParamTuningMutation
            .mutate()
        }}
        isTuningPending={
          evaluation
            .runAgentParamTuningMutation
            .isPending
        }
        isTuningError={
          evaluation
            .runAgentParamTuningMutation
            .isError
        }
        tuningError={
          evaluation
            .runAgentParamTuningMutation
            .error
        }
        tuningData={
          evaluation
            .runAgentParamTuningMutation
            .data
        }
        recommendation={
          evaluation
            .agentParamRecommendation
        }
        onApplyRecommendation={
          evaluation
            .handleApplyRecommendedAgentConfig
        }
        isApplyRecommendationPending={
          evaluation
            .updateAgentSettingsMutation
            .isPending
        }
        isApplyRecommendationError={
          evaluation
            .updateAgentSettingsMutation
            .isError
        }
        applyRecommendationError={
          evaluation
            .updateAgentSettingsMutation
            .error
        }
      />

      <RetrievalExperimentSection
        evaluation={evaluation}
      />

      <EvaluationSummarySection
        evaluation={evaluation}
      />

      <CodeEvalAnalysisSection
        evaluation={evaluation}
      />

      <OptimizationExperimentSection
        evaluation={evaluation}
      />

      <RagEvaluationRecordsSection
        evaluation={evaluation}
      />

      <RagEvaluationCasesSection
        evaluation={evaluation}
      />

      <RagEvaluationRunsSection
        evaluation={evaluation}
      />
    </div>
  )
}
