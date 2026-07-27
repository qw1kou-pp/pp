import {
  useState,
} from "react"

import {
  DocumentListSection,
} from "./DocumentListSection"
import {
  KnowledgeBaseUploadSection,
} from "./KnowledgeBaseUploadSection"
import {
  useKnowledgeBaseOverview,
} from "./useKnowledgeBaseOverview"

type Props = {
  knowledgeBaseId: string
}

export function KnowledgeBaseOverviewTab({
  knowledgeBaseId,
}: Props) {
  const overview =
    useKnowledgeBaseOverview({
      knowledgeBaseId,
    })

  const [
    isDocumentListOpen,
    setIsDocumentListOpen,
  ] = useState(false)

  return (
    <div className="space-y-6">
      <KnowledgeBaseUploadSection
        overview={overview}
      />

      <DocumentListSection
        overview={overview}
        isOpen={
          isDocumentListOpen
        }
        onToggle={() => {
          setIsDocumentListOpen(
            (current) => !current,
          )
        }}
      />
    </div>
  )
}
