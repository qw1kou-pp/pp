import { DocumentsService } from "@/client"
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import {
  useRef,
  useState,
} from "react"

import {
  documentChunksQueryOptions,
  knowledgeBaseDocumentsQueryOptions,
  knowledgeBaseOverviewKeys,
} from "./knowledgeBaseOverviewQueries"

type UseKnowledgeBaseOverviewOptions = {
  knowledgeBaseId: string
}

export function useKnowledgeBaseOverview({
  knowledgeBaseId,
}: UseKnowledgeBaseOverviewOptions) {
  const queryClient = useQueryClient()

  const fileInputRef =
    useRef<HTMLInputElement | null>(
      null,
    )

  const repositoryZipInputRef =
    useRef<HTMLInputElement | null>(
      null,
    )

  const [
    selectedFile,
    setSelectedFile,
  ] = useState<File | null>(null)

  const [
    selectedRepositoryZip,
    setSelectedRepositoryZip,
  ] = useState<File | null>(null)

  const [
    expandedDocumentId,
    setExpandedDocumentId,
  ] = useState<string | null>(null)

  const documentsQuery = useQuery(
    knowledgeBaseDocumentsQueryOptions(
      knowledgeBaseId,
    ),
  )

  const chunksQuery = useQuery({
    ...documentChunksQueryOptions(
      expandedDocumentId || "",
    ),

    enabled:
      Boolean(
        expandedDocumentId,
      ),
  })

  const uploadDocumentMutation =
    useMutation({
      mutationFn: (file: File) =>
        DocumentsService.uploadDocument({
          knowledgeBaseId,
          formData: {
            file,
          },
        }),

      onSuccess: async () => {
        setSelectedFile(null)

        if (fileInputRef.current) {
          fileInputRef.current.value = ""
        }

        await queryClient.invalidateQueries({
          queryKey:
            knowledgeBaseOverviewKeys.documents(
              knowledgeBaseId,
            ),
        })
      },
    })

  const uploadCodeRepositoryZipMutation =
    useMutation({
      mutationFn: (file: File) =>
        DocumentsService.uploadCodeRepositoryZip({
          knowledgeBaseId,
          formData: {
            file,
          },
        }),

      onSuccess: async () => {
        setSelectedRepositoryZip(null)

        if (
          repositoryZipInputRef.current
        ) {
          repositoryZipInputRef.current.value =
            ""
        }

        await queryClient.invalidateQueries({
          queryKey:
            knowledgeBaseOverviewKeys.documents(
              knowledgeBaseId,
            ),
        })
      },
    })

  const deleteDocumentMutation =
    useMutation({
      mutationFn: (
        documentId: string,
      ) =>
        DocumentsService.deleteDocument({
          documentId,
        }),

      onSuccess: async (
        _result,
        documentId,
      ) => {
        if (
          expandedDocumentId
          === documentId
        ) {
          setExpandedDocumentId(null)
        }

        queryClient.removeQueries({
          queryKey:
            knowledgeBaseOverviewKeys.chunks(
              documentId,
            ),
        })

        await queryClient.invalidateQueries({
          queryKey:
            knowledgeBaseOverviewKeys.documents(
              knowledgeBaseId,
            ),
        })
      },
    })

  const handleUploadDocument = () => {
    if (!selectedFile) {
      window.alert("请先选择文件")
      return
    }

    uploadDocumentMutation.mutate(
      selectedFile,
    )
  }

  const handleUploadRepositoryZip = () => {
    if (!selectedRepositoryZip) {
      window.alert(
        "请先选择代码仓库 zip 文件",
      )
      return
    }

    uploadCodeRepositoryZipMutation.mutate(
      selectedRepositoryZip,
    )
  }

  const handleToggleDocument = (
    documentId: string,
  ) => {
    setExpandedDocumentId(
      (currentDocumentId) =>
        currentDocumentId
          === documentId
          ? null
          : documentId,
    )
  }

  const handleDeleteDocument = (
    documentId: string,
  ) => {
    const confirmed =
      window.confirm(
        "确定删除这个文档吗？",
      )

    if (!confirmed) {
      return
    }

    deleteDocumentMutation.mutate(
      documentId,
    )
  }

  const handleDownloadDocument = async (
    documentId: string,
    filename: string,
  ) => {
    const token =
      localStorage.getItem(
        "access_token",
      )

    if (!token) {
      window.alert("请先登录")
      return
    }

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}/api/v1/documents/${documentId}/download`,
        {
          headers: {
            Authorization:
              `Bearer ${token}`,
          },
        },
      )

      if (!response.ok) {
        throw new Error(
          `Document download failed: ${response.status}`,
        )
      }

      const blob =
        await response.blob()

      const objectUrl =
        window.URL.createObjectURL(
          blob,
        )

      const link =
        window.document.createElement(
          "a",
        )

      link.href = objectUrl
      link.download = filename
      link.style.display = "none"

      window.document.body.appendChild(
        link,
      )

      link.click()
      link.remove()

      window.URL.revokeObjectURL(
        objectUrl,
      )
    } catch (error) {
      console.error(
        "Document download failed",
        error,
      )

      window.alert("下载失败")
    }
  }

  return {
    fileInputRef,
    repositoryZipInputRef,

    selectedFile,
    setSelectedFile,

    selectedRepositoryZip,
    setSelectedRepositoryZip,

    expandedDocumentId,

    documentsQuery,
    chunksQuery,

    uploadDocumentMutation,
    uploadCodeRepositoryZipMutation,
    deleteDocumentMutation,

    handleUploadDocument,
    handleUploadRepositoryZip,
    handleToggleDocument,
    handleDeleteDocument,
    handleDownloadDocument,
  }
}

export type KnowledgeBaseOverviewController =
  ReturnType<
    typeof useKnowledgeBaseOverview
  >
