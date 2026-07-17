import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { useRef, useState } from "react"

import { DocumentsService, KnowledgeBasesService } from "@/client"

export const Route = createFileRoute("/_layout/1")({
  component: KnowledgeBaseDetailPage,
})

function formatFileSize(size: number) {
  if (size < 1024) {
    return `${size} B`
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }

  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function KnowledgeBaseDetailPage() {
  const { knowledgeBaseId } = Route.useParams()
  const queryClient = useQueryClient()

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [expandedDocumentId, setExpandedDocumentId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [chatQuestion, setChatQuestion] = useState("")
  const [semanticQuery, setSemanticQuery] = useState("")
  const [ragRunKeyword, setRagRunKeyword] = useState("")
  const [evalQuestion, setEvalQuestion] = useState("")
  const [evalKeywords, setEvalKeywords] = useState("")
  const [evalSourceFilename, setEvalSourceFilename] = useState("")
  const [evalNote, setEvalNote] = useState("")
  const [evalRunKeyword, setEvalRunKeyword] = useState("")
  const [evalFailedOnly, setEvalFailedOnly] = useState(false)
  const [evalFailureType, setEvalFailureType] = useState<
    "all" | "keyword" | "source" | "error" | "zero"
  >("all")

  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const {
    data: knowledgeBase,
    isPending: isKnowledgeBasePending,
    isError: isKnowledgeBaseError,
  } = useQuery({
    queryKey: ["knowledge-base", knowledgeBaseId],
    queryFn: () =>
      KnowledgeBasesService.readKnowledgeBase({
        id: knowledgeBaseId,
      }),
  })

  const {
    data: documents,
    isPending: isDocumentsPending,
    isError: isDocumentsError,
  } = useQuery({
    queryKey: ["documents", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readDocumentsByKnowledgeBase({
        knowledgeBaseId,
        skip: 0,
        limit: 100,
      }),
  })

  const {
    data: chunks,
    isPending: isChunksPending,
    isError: isChunksError,
  } = useQuery({
    queryKey: ["document-chunks", expandedDocumentId],
    enabled: expandedDocumentId !== null,
    queryFn: () => {
      if (!expandedDocumentId) {
        throw new Error("Document id is required")
      }

      return DocumentsService.readDocumentChunks({
        documentId: expandedDocumentId,
        skip: 0,
        limit: 100,
      })
    },
  })

  const ragRunsQuery = useQuery({
    queryKey: ["rag-runs", knowledgeBaseId, ragRunKeyword],
    queryFn: () =>
      DocumentsService.readKnowledgeBaseRagRuns({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
        keyword: ragRunKeyword.trim() || undefined,
      }),
  })

  const ragEvalCasesQuery = useQuery({
    queryKey: ["rag-eval-cases", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagEvalCases({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
      }),
  })

  const ragEvalRunsQuery = useQuery({
    queryKey: [
      "rag-eval-runs",
      knowledgeBaseId,
      evalRunKeyword,
      evalFailedOnly,
      evalFailureType,
    ],
    queryFn: () =>
      DocumentsService.readRagEvalRuns({
        knowledgeBaseId,
        skip: 0,
        limit: 20,
        keyword: evalRunKeyword.trim() || undefined,
        failedOnly: evalFailedOnly || undefined,
        keywordHit: evalFailureType === "keyword" ? false : undefined,
        sourceHit: evalFailureType === "source" ? false : undefined,
        errorOnly: evalFailureType === "error" ? true : undefined,
        maxScore: evalFailureType === "zero" ? 0 : undefined,
      }),
  })

  const ragEvalSummaryQuery = useQuery({
    queryKey: ["rag-eval-summary", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagEvalSummary({
        knowledgeBaseId,
        limit: 200,
      }),
  })

  const ragEvalFailureAnalysisQuery = useQuery({
    queryKey: ["rag-eval-failure-analysis", knowledgeBaseId],
    queryFn: () =>
      DocumentsService.readRagEvalFailureAnalysis({
        knowledgeBaseId,
        limit: 200,
        recentLimit: 10,
      }),
  })

  const uploadDocumentMutation = useMutation({
    mutationFn: (file: File) =>
      DocumentsService.uploadDocument({
        knowledgeBaseId,
        formData: {
          file,
        },
      }),
    onSuccess: () => {
      setSelectedFile(null)

      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }

      queryClient.invalidateQueries({
        queryKey: ["documents", knowledgeBaseId],
      })
    },
  })

  const deleteDocumentMutation = useMutation({
    mutationFn: (documentId: string) =>
      DocumentsService.deleteDocument({
        documentId,
      }),
    onSuccess: () => {
      setExpandedDocumentId(null)

      queryClient.invalidateQueries({
        queryKey: ["documents", knowledgeBaseId],
      })
    },
  })

  const searchKnowledgeBaseMutation = useMutation({
    mutationFn: (query: string) =>
      DocumentsService.searchKnowledgeBaseChunks({
        knowledgeBaseId,
        requestBody: {
          query,
          limit: 10,
        },
      }),
  })


  const semanticSearchKnowledgeBaseMutation = useMutation({
    mutationFn: (query: string) =>
      DocumentsService.semanticSearchKnowledgeBaseChunks({
        knowledgeBaseId,
        requestBody: {
          query,
          top_k: 5,
        },
      }),
  })


  const backfillEmbeddingsMutation = useMutation({
    mutationFn: () =>
      DocumentsService.backfillKnowledgeBaseEmbeddings({
        knowledgeBaseId,
        requestBody: {
          limit: 20,
          retry_failed: true,
          force: false,
        },
      }),
  })

  const chatKnowledgeBaseMutation = useMutation({
    mutationFn: (question: string) =>
      DocumentsService.chatWithKnowledgeBase({
        knowledgeBaseId,
        requestBody: {
          question,
          top_k: 5,
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-runs", knowledgeBaseId],
      })
    },
  })

  const deleteRagRunMutation = useMutation({
    mutationFn: (ragRunId: string) =>
      DocumentsService.deleteRagRun({
        ragRunId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-runs", knowledgeBaseId],
      })
    },
  })


  const createRagEvalCaseMutation = useMutation({
    mutationFn: () =>
      DocumentsService.createRagEvalCase({
        knowledgeBaseId,
        requestBody: {
          question: evalQuestion.trim(),
          expected_keywords: evalKeywords
            .split(/[,，\n]/)
            .map((item) => item.trim())
            .filter(Boolean),
          expected_source_filename: evalSourceFilename.trim() || null,
          note: evalNote.trim() || null,
        },
      }),
    onSuccess: () => {
      setEvalQuestion("")
      setEvalKeywords("")
      setEvalSourceFilename("")
      setEvalNote("")

      queryClient.invalidateQueries({
        queryKey: ["rag-eval-cases", knowledgeBaseId],
      })
    },
  })

  const runRagEvalCaseMutation = useMutation({
    mutationFn: (evalCaseId: string) =>
      DocumentsService.runRagEvalCase({
        evalCaseId,
        requestBody: {
          top_k: 5,
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-runs", knowledgeBaseId],
      })
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-summary", knowledgeBaseId],
      })
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-failure-analysis", knowledgeBaseId],
      })
    },
  })

  const deleteRagEvalCaseMutation = useMutation({
    mutationFn: (evalCaseId: string) =>
      DocumentsService.deleteRagEvalCase({
        evalCaseId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-cases", knowledgeBaseId],
      })

      queryClient.invalidateQueries({
        queryKey: ["rag-eval-runs", knowledgeBaseId],
      })
    },
  })

  const runAllRagEvalCasesMutation = useMutation({
    mutationFn: () =>
      DocumentsService.runAllRagEvalCases({
        knowledgeBaseId,
        requestBody: {
          top_k: 5,
          limit: 100,
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-runs", knowledgeBaseId],
      })

      queryClient.invalidateQueries({
        queryKey: ["rag-eval-summary", knowledgeBaseId],
      })
      queryClient.invalidateQueries({
        queryKey: ["rag-eval-failure-analysis", knowledgeBaseId],
      })
    },
  })

  const handleUpload = () => {
    if (!selectedFile) {
      alert("请先选择文件")
      return
    }

    uploadDocumentMutation.mutate(selectedFile)
  }

  const handleToggleChunks = (documentId: string) => {
    if (expandedDocumentId === documentId) {
      setExpandedDocumentId(null)
      return
    }

    setExpandedDocumentId(documentId)
  }

  const handleSearch = () => {
    const query = searchQuery.trim()

    if (!query) {
      alert("请输入要检索的内容")
      return
    }

    searchKnowledgeBaseMutation.mutate(query)
  }

  const handleDeleteRagRun = (ragRunId: string) => {
    const confirmed = window.confirm("确定要删除这条 RAG 问答历史吗？")

    if (!confirmed) {
      return
    }

    deleteRagRunMutation.mutate(ragRunId)
  }

  const handleSemanticSearch = () => {
    const query = semanticQuery.trim()

    if (!query) {
      alert("请输入要语义检索的内容")
      return
    }

    semanticSearchKnowledgeBaseMutation.mutate(query)
  }

  const handleBackfillEmbeddings = () => {
    backfillEmbeddingsMutation.mutate()
  }

  const handleChat = () => {
    const question = chatQuestion.trim()

    if (!question) {
      alert("请输入要提问的内容")
      return
    }

    chatKnowledgeBaseMutation.mutate(question)
  }

  const handleCreateRagEvalCase = () => {
    if (!evalQuestion.trim()) {
      alert("请输入评测问题")
      return
    }

    createRagEvalCaseMutation.mutate()
  }

  const handleRunRagEvalCase = (evalCaseId: string) => {
    runRagEvalCaseMutation.mutate(evalCaseId)
  }

  const handleRunAllRagEvalCases = () => {
    const confirmed = window.confirm(
      "确定要运行当前知识库下的全部评测样例吗？这可能需要等待一段时间。"
    )

    if (!confirmed) {
      return
    }

    runAllRagEvalCasesMutation.mutate()
  }

  const handleDeleteRagEvalCase = (evalCaseId: string) => {
    const confirmed = window.confirm("确定要删除这条评测样例吗？")

    if (!confirmed) {
      return
    }

    deleteRagEvalCaseMutation.mutate(evalCaseId)
  }

  const handleDownload = async (documentId: string, filename: string) => {
    const token = localStorage.getItem("access_token")

    if (!token) {
      alert("请先登录")
      return
    }

    const response = await fetch(
      `${import.meta.env.VITE_API_URL}/api/v1/documents/${documentId}/download`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )

    if (!response.ok) {
      alert("下载失败")
      return
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)

    const link = window.document.createElement("a")
    link.href = url
    link.download = filename
    link.click()

    window.URL.revokeObjectURL(url)
  }

  if (isKnowledgeBasePending || isDocumentsPending) {
    return <div className="p-6">正在加载知识库详情...</div>
  }

  if (isKnowledgeBaseError) {
    return <div className="p-6">知识库加载失败</div>
  }

  if (isDocumentsError) {
    return <div className="p-6">文档列表加载失败</div>
  }

  if (!knowledgeBase || !documents) {
    return <div className="p-6">暂无数据</div>
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <Link to="/knowledge-bases" className="text-sm underline">
          返回知识库列表
        </Link>
      </div>

      <div className="border rounded-lg p-4 space-y-2">
        <h1 className="text-2xl font-bold">{knowledgeBase.name}</h1>

        <p className="text-sm text-gray-500">
          {knowledgeBase.description || "暂无描述"}
        </p>

        <p className="text-xs text-gray-400">知识库 ID：{knowledgeBase.id}</p>
      </div>

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">上传文档</h2>
          <p className="text-sm text-gray-500">
            支持上传 pdf、txt、md、docx 文件。目前 txt、md 会自动解析并切分。
          </p>
        </div>

        <div className="flex gap-3 items-center">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md,.docx"
            onChange={(event) => {
              const file = event.target.files?.[0] || null
              setSelectedFile(file)
            }}
          />

          <button
            className="border rounded px-4 py-2"
            onClick={handleUpload}
            disabled={uploadDocumentMutation.isPending}
          >
            {uploadDocumentMutation.isPending ? "上传中..." : "上传"}
          </button>
        </div>

        {selectedFile ? (
          <div className="text-sm text-gray-500">
            当前选择：{selectedFile.name}，大小：
            {formatFileSize(selectedFile.size)}
          </div>
        ) : null}

        {uploadDocumentMutation.isError ? (
          <div className="text-sm text-red-500">
            上传失败，请检查文件类型、文件大小或登录状态。
          </div>
        ) : null}
      </div>

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">知识库检索测试</h2>
          <p className="text-sm text-gray-500">
            这里先用关键词检索 DocumentChunk，后面可以替换成向量检索。
          </p>
        </div>

        <div className="flex gap-3">
          <input
            className="border rounded px-3 py-2 flex-1"
            placeholder="请输入关键词，例如：FastAPI 路由"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                handleSearch()
              }
            }}
          />

          <button
            className="border rounded px-4 py-2"
            onClick={handleSearch}
            disabled={searchKnowledgeBaseMutation.isPending}
          >
            {searchKnowledgeBaseMutation.isPending ? "检索中..." : "检索"}
          </button>
        </div>

        {searchKnowledgeBaseMutation.isError ? (
          <div className="text-sm text-red-500">检索失败，请检查后端接口。</div>
        ) : null}

        {searchKnowledgeBaseMutation.data ? (
          <div className="space-y-3">
            <div className="text-sm text-gray-500">
              共找到 {searchKnowledgeBaseMutation.data.count} 条结果，当前展示{" "}
              {searchKnowledgeBaseMutation.data.data.length} 条。
            </div>

            {searchKnowledgeBaseMutation.data.data.length === 0 ? (
              <div className="text-sm text-gray-500">暂无匹配结果</div>
            ) : (
              searchKnowledgeBaseMutation.data.data.map((result) => (
                <div
                  key={result.chunk_id}
                  className="border border-gray-700 rounded p-3 bg-neutral-900 text-gray-100 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium">
                      来源文件：{result.original_filename} ｜ Chunk{" "}
                      {result.chunk_index}
                    </div>

                    <div className="text-xs text-gray-400">
                      命中次数：{result.match_count} ｜ 长度：{result.content_length}
                    </div>
                  </div>

                  <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                    {result.content}
                  </pre>
                </div>
              ))
            )}
          </div>
        ) : null}
      </div>

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">语义检索测试</h2>
          <p className="text-sm text-gray-500">
          这里会把你的问题转成 embedding，然后和 DocumentChunk 的 embedding
          计算相似度，返回语义最接近的 chunk。
          </p>
        </div>

        <div className="flex gap-3">
          <input
          className="border rounded px-3 py-2 flex-1"
          placeholder="请输入问题，例如：用户登录状态应该怎么保存？"
          value={semanticQuery}
          onChange={(event) => setSemanticQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              handleSemanticSearch()
            }
          }}
        />

        <button
          className="border rounded px-4 py-2"
          onClick={handleSemanticSearch}
          disabled={semanticSearchKnowledgeBaseMutation.isPending}
        >
          {semanticSearchKnowledgeBaseMutation.isPending ? "检索中..." : "语义检索"}
        </button>
      </div>

      <div className="flex items-center gap-3">
        <button
          className="border rounded px-4 py-2"
          onClick={handleBackfillEmbeddings}
          disabled={backfillEmbeddingsMutation.isPending}
        >
          {backfillEmbeddingsMutation.isPending
            ? "回填中..."
            : "回填旧数据 Embedding"}
        </button>

        <span className="text-xs text-gray-500">
          如果旧文档没有 embedding，可以先点击这里回填。
        </span>
      </div>

      {backfillEmbeddingsMutation.isError ? (
        <div className="text-sm text-red-500">
          Embedding 回填失败，请检查后端日志或 API Key。
        </div>
      ) : null}

      {backfillEmbeddingsMutation.data ? (
        <div className="text-sm text-gray-500">
          回填结果：本次处理 {backfillEmbeddingsMutation.data.processed} 个，
          成功 {backfillEmbeddingsMutation.data.embedded} 个，失败{" "}
          {backfillEmbeddingsMutation.data.failed} 个，剩余{" "}
          {backfillEmbeddingsMutation.data.remaining} 个。模型：
          {backfillEmbeddingsMutation.data.model}
        </div>
      ) : null}

      {semanticSearchKnowledgeBaseMutation.isError ? (
        <div className="text-sm text-red-500">
          语义检索失败，请检查后端 semantic-search 接口或 embedding 配置。
        </div>
      ) : null}

      {semanticSearchKnowledgeBaseMutation.data ? (
        <div className="space-y-3">
          <div className="text-sm text-gray-500">
            共找到 {semanticSearchKnowledgeBaseMutation.data.count} 条语义检索结果。
          </div>

          {semanticSearchKnowledgeBaseMutation.data.data.length === 0 ? (
            <div className="text-sm text-gray-500">
              暂无语义检索结果。可能是当前知识库还没有生成 embedding。
            </div>
          ) : (
            semanticSearchKnowledgeBaseMutation.data.data.map((result) => (
              <div
                key={result.chunk_id}
                className="border border-gray-700 rounded p-3 bg-neutral-900 text-gray-100 space-y-2"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium">
                    来源文件：{result.original_filename} ｜ Chunk{" "}
                    {result.chunk_index}
                  </div>

                  <div className="text-xs text-gray-400">
                    相似度：{result.similarity.toFixed(4)} ｜ 长度：
                    {result.content_length}
                  </div>
                </div>

                <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                  {result.content}
                </pre>
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">RAG 问答测试</h2>
          <p className="text-sm text-gray-500">
            这里会先从当前知识库检索相关 chunk，再基于检索结果生成回答。
            当前版本是 RAG Chat v0，先返回资料型回答，后续可以接入大模型。
          </p>
        </div>

        <div className="flex gap-3">
          <input
            className="border rounded px-3 py-2 flex-1"
            placeholder="请输入问题，例如：这份文档主要讲了什么？"
            value={chatQuestion}
            onChange={(event) => setChatQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                handleChat()
              }
            }}
          />

          <button
            className="border rounded px-4 py-2"
            onClick={handleChat}
            disabled={chatKnowledgeBaseMutation.isPending}
          >
            {chatKnowledgeBaseMutation.isPending ? "回答中..." : "提问"}
          </button>
        </div>

        {chatKnowledgeBaseMutation.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            问答失败：{JSON.stringify(chatKnowledgeBaseMutation.error, null, 2)}
          </div>
        ) : null}

        {chatKnowledgeBaseMutation.data ? (
          <div className="space-y-4">
            <div className="border border-gray-700 rounded p-4 bg-neutral-900 text-gray-100 space-y-3">
              <div className="font-medium">回答</div>

              <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                {chatKnowledgeBaseMutation.data.answer}
              </pre>
            </div>

            <div className="border rounded p-4 space-y-3">
              <div className="font-medium">引用来源</div>

              {chatKnowledgeBaseMutation.data.sources.length === 0 ? (
                <div className="text-sm text-gray-500">
                  暂无引用来源。说明当前知识库没有检索到相关 chunk。
                </div>
              ) : (
                chatKnowledgeBaseMutation.data.sources.map((source) => (
                  <div
                    key={source.chunk_id}
                    className="border border-gray-700 rounded p-3 bg-neutral-900 text-gray-100 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-medium">
                        来源文件：{source.original_filename} ｜ Chunk{" "}
                        {source.chunk_index}
                      </div>

                      <div className="text-xs text-gray-400">
                        {source.retrieval_type === "hybrid" ? (
                          <>
                            检索方式：混合检索 ｜ 相似度：
                            {source.similarity?.toFixed(4)} ｜ 关键词命中：
                            {source.match_count} ｜ 长度：{source.content_length}
                          </>
                        ) : source.retrieval_type === "semantic" ? (
                          <>
                            检索方式：语义检索 ｜ 相似度：
                            {source.similarity?.toFixed(4)} ｜ 长度：{source.content_length}
                          </>
                        ) : (
                          <>
                            检索方式：关键词检索 ｜ 命中次数：{source.match_count} ｜ 长度：
                            {source.content_length}
                          </>
                        )}
                      </div>
                    </div>

                    <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                      {source.content}
                    </pre>
                  </div>
                ))
              )}
            </div>

            <div className="border rounded p-4 space-y-2">
              <div className="font-medium">执行过程 Trace</div>

              <div className="text-sm text-gray-500">
                {chatKnowledgeBaseMutation.data.trace.join(" → ")}
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <div className="border rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">RAG 问答历史</h2>
            <p className="text-sm text-gray-500">
              这里展示当前知识库最近的 RAG 问答记录，包括问题、回答、来源和执行过程。
            </p>
          </div>

          <button
            className="border rounded px-3 py-1 text-sm"
            onClick={() =>
              queryClient.invalidateQueries({
                queryKey: ["rag-runs", knowledgeBaseId],
              })
            }
          >
            刷新历史
          </button>
        </div>

        <div className="flex gap-3">
          <input
            className="border rounded px-3 py-2 flex-1"
            placeholder="搜索历史记录，例如：FastAPI、JWT、登录、hybrid"
            value={ragRunKeyword}
            onChange={(event) => setRagRunKeyword(event.target.value)}
          />

          {ragRunKeyword.trim() ? (
            <button
              className="border rounded px-4 py-2"
              onClick={() => setRagRunKeyword("")}
            >
              清空
            </button>
          ) : null}
        </div>

        {deleteRagRunMutation.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            删除失败：
            {JSON.stringify(deleteRagRunMutation.error, null, 2)}
          </div>
        ) : null}

        {ragRunsQuery.isLoading ? (
          <div className="text-sm text-gray-500">正在加载问答历史...</div>
        ) : null}

        {ragRunsQuery.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            问答历史加载失败：
            {JSON.stringify(ragRunsQuery.error, null, 2)}
          </div>
        ) : null}

        {ragRunsQuery.data ? (
          <div className="space-y-3">
            <div className="text-sm text-gray-500">
              共 {ragRunsQuery.data.count} 条记录，当前展示{" "}
              {ragRunsQuery.data.data.length} 条。
            </div>

            {ragRunsQuery.data.data.length === 0 ? (
              <div className="text-sm text-gray-500">
                暂无问答历史。你可以先在上面的 RAG 问答测试里提一个问题。
              </div>
            ) : (
              ragRunsQuery.data.data.map((run) => (
                <div
                  key={run.id}
                  className="border border-gray-700 rounded p-4 bg-neutral-900 text-gray-100 space-y-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium">问题：{run.question}</div>

                    <div className="flex items-center gap-3">
                      <div className="text-xs text-gray-400">
                        检索方式：{run.retrieval_type} ｜ 耗时：
                        {run.latency_ms ?? "-"} ms
                      </div>

                      <button
                        className="border border-red-500 text-red-400 rounded px-2 py-1 text-xs"
                        onClick={() => handleDeleteRagRun(run.id)}
                        disabled={deleteRagRunMutation.isPending}
                      >
                        删除
                      </button>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="text-sm font-medium text-gray-200">回答</div>
                    <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                      {run.answer}
                    </pre>
                  </div>

                  <details className="space-y-2">
                    <summary className="cursor-pointer text-sm text-gray-300">
                      查看引用来源（{run.sources.length}）
                    </summary>

                    <div className="space-y-2 pt-2">
                      {run.sources.length === 0 ? (
                        <div className="text-sm text-gray-500">
                          当前记录没有引用来源。
                        </div>
                      ) : (
                        run.sources.map((source) => (
                          <div
                            key={source.chunk_id}
                            className="border border-gray-700 rounded p-3 bg-black text-gray-100 space-y-2"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div className="text-sm font-medium">
                                来源文件：{source.original_filename} ｜ Chunk{" "}
                                {source.chunk_index}
                              </div>

                              <div className="text-xs text-gray-400">
                                {source.retrieval_type === "hybrid" ? (
                                  <>
                                    混合检索 ｜ 相似度：
                                    {source.similarity?.toFixed(4)} ｜ 关键词命中：
                                    {source.match_count} ｜ 长度：
                                    {source.content_length}
                                  </>
                                ) : source.retrieval_type === "semantic" ? (
                                  <>
                                    语义检索 ｜ 相似度：
                                    {source.similarity?.toFixed(4)} ｜ 长度：
                                    {source.content_length}
                                  </>
                                ) : (
                                  <>
                                    关键词检索 ｜ 命中次数：{source.match_count} ｜
                                    长度：{source.content_length}
                                  </>
                                )}
                              </div>
                            </div>

                            <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                              {source.content}
                            </pre>
                          </div>
                        ))
                      )}
                    </div>
                  </details>

                  <details>
                    <summary className="cursor-pointer text-sm text-gray-300">
                      查看执行过程 Trace
                    </summary>

                    <div className="pt-2 text-sm text-gray-400">
                      {run.trace.length > 0 ? run.trace.join(" → ") : "暂无 trace"}
                    </div>
                  </details>

                  {run.created_at ? (
                    <div className="text-xs text-gray-500">
                      创建时间：{new Date(run.created_at).toLocaleString()}
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </div>
        ) : null}
      </div>

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">RAG 评测面板</h2>
          <p className="text-sm text-gray-500">
            这里可以创建固定测试问题，运行 RAG 评测，并查看关键词命中、来源命中、得分和耗时。
          </p>
        </div>

      <div className="border rounded p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold">评测统计概览</h3>
            <p className="text-sm text-gray-500">
                统计最近的 RAG 评测运行结果，用于观察整体检索与回答效果。
            </p>
          </div>

          <div className="flex gap-2">
            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-eval-summary", knowledgeBaseId],
                })
              }
            >
              刷新统计
            </button>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={handleRunAllRagEvalCases}
              disabled={runAllRagEvalCasesMutation.isPending}
            >
              {runAllRagEvalCasesMutation.isPending
                ? "批量运行中..."
                : "运行全部评测"}
            </button>
          </div>
        </div>

        {ragEvalSummaryQuery.isLoading ? (
          <div className="text-sm text-gray-500">正在加载评测统计...</div>
        ) : null}

        {ragEvalSummaryQuery.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            评测统计加载失败：
            {JSON.stringify(ragEvalSummaryQuery.error, null, 2)}
          </div>
        ) : null}

        {runAllRagEvalCasesMutation.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            批量运行评测失败：
            {JSON.stringify(runAllRagEvalCasesMutation.error, null, 2)}
          </div>
        ) : null}

        {runAllRagEvalCasesMutation.data ? (
          <div className="text-sm text-gray-500">
            批量运行结果：共 {runAllRagEvalCasesMutation.data.total_cases} 条样例，
            成功运行 {runAllRagEvalCasesMutation.data.ran} 条，失败{" "}
            {runAllRagEvalCasesMutation.data.failed} 条。
          </div>
        ) : null}

        {ragEvalSummaryQuery.data ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="border rounded p-3 bg-neutral-900 text-gray-100">
              <div className="text-xs text-gray-400">总评测次数</div>
              <div className="text-xl font-semibold">
                {ragEvalSummaryQuery.data.total_runs}
              </div>
            </div>

            <div className="border rounded p-3 bg-neutral-900 text-gray-100">
              <div className="text-xs text-gray-400">平均分</div>
              <div className="text-xl font-semibold">
                {ragEvalSummaryQuery.data.average_score === null
                  ? "-"
                  : ragEvalSummaryQuery.data.average_score.toFixed(2)}
              </div>
            </div>

            <div className="border rounded p-3 bg-neutral-900 text-gray-100">
              <div className="text-xs text-gray-400">关键词命中率</div>
              <div className="text-xl font-semibold">
                {ragEvalSummaryQuery.data.keyword_hit_rate === null
                  ? "-"
                  : `${(ragEvalSummaryQuery.data.keyword_hit_rate * 100).toFixed(1)}%`}
              </div>
            </div>

            <div className="border rounded p-3 bg-neutral-900 text-gray-100">
              <div className="text-xs text-gray-400">来源命中率</div>
              <div className="text-xl font-semibold">
                {ragEvalSummaryQuery.data.source_hit_rate === null
                  ? "-"
                  : `${(ragEvalSummaryQuery.data.source_hit_rate * 100).toFixed(1)}%`}
              </div>
            </div>

            <div className="border rounded p-3 bg-neutral-900 text-gray-100">
              <div className="text-xs text-gray-400">平均耗时</div>
              <div className="text-xl font-semibold">
                {ragEvalSummaryQuery.data.average_latency_ms === null
                  ? "-"
                  : `${ragEvalSummaryQuery.data.average_latency_ms.toFixed(0)} ms`}
              </div>
            </div>

            <div className="border rounded p-3 bg-neutral-900 text-gray-100">
              <div className="text-xs text-gray-400">最高分</div>
              <div className="text-xl font-semibold">
                {ragEvalSummaryQuery.data.max_score === null
                  ? "-"
                  : ragEvalSummaryQuery.data.max_score.toFixed(2)}
              </div>
            </div>

            <div className="border rounded p-3 bg-neutral-900 text-gray-100">
              <div className="text-xs text-gray-400">最低分</div>
              <div className="text-xl font-semibold">
                {ragEvalSummaryQuery.data.min_score === null
                  ? "-"
                  : ragEvalSummaryQuery.data.min_score.toFixed(2)}
              </div>
            </div>

            <div className="border rounded p-3 bg-neutral-900 text-gray-100">
              <div className="text-xs text-gray-400">最新评测时间</div>
              <div className="text-sm font-medium">
                {ragEvalSummaryQuery.data.latest_run_at
                  ? new Date(ragEvalSummaryQuery.data.latest_run_at).toLocaleString()
                  : "-"}
              </div>
            </div>
          </div>
        ) : null}
      </div>


      <div className="border rounded p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold">失败样例分析</h3>
            <p className="text-sm text-gray-500">
              这里统计最近评测中的失败样例，帮助定位是关键词、来源还是运行错误导致的问题。
            </p>
          </div>

          <button
            className="border rounded px-3 py-1 text-sm"
            onClick={() =>
              queryClient.invalidateQueries({
                queryKey: ["rag-eval-failure-analysis", knowledgeBaseId],
              })
            }
          >
            刷新分析
          </button>
        </div>

        {ragEvalFailureAnalysisQuery.isLoading ? (
          <div className="text-sm text-gray-500">正在加载失败分析...</div>
        ) : null}

        {ragEvalFailureAnalysisQuery.isError ? (
          <div className="text-sm text-red-500 whitespace-pre-wrap">
            失败分析加载失败：
            {JSON.stringify(ragEvalFailureAnalysisQuery.error, null, 2)}
          </div>
        ) : null}

        {ragEvalFailureAnalysisQuery.data ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                <div className="text-xs text-gray-400">失败次数</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.failed_runs}
                  </div>
                </div>

                <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                  <div className="text-xs text-gray-400">失败率</div>
                  <div className="text-xl font-semibold">
                    {ragEvalFailureAnalysisQuery.data.failure_rate === null
                      ? "-"
                      : `${(ragEvalFailureAnalysisQuery.data.failure_rate * 100).toFixed(1)}%`}
                    </div>
                  </div>

                  <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                    <div className="text-xs text-gray-400">关键词未命中</div>
                    <div className="text-xl font-semibold">
                      {ragEvalFailureAnalysisQuery.data.keyword_miss_count}
                    </div>
                  </div>

                  <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                    <div className="text-xs text-gray-400">来源未命中</div>
                    <div className="text-xl font-semibold">
                      {ragEvalFailureAnalysisQuery.data.source_miss_count}
                    </div>
                  </div>

                  <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                    <div className="text-xs text-gray-400">运行错误</div>
                    <div className="text-xl font-semibold">
                      {ragEvalFailureAnalysisQuery.data.error_count}
                    </div>
                  </div>

                  <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                    <div className="text-xs text-gray-400">低分样例</div>
                    <div className="text-xl font-semibold">
                      {ragEvalFailureAnalysisQuery.data.low_score_count}
                    </div>
                  </div>

                  <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                    <div className="text-xs text-gray-400">零分样例</div>
                    <div className="text-xl font-semibold">
                      {ragEvalFailureAnalysisQuery.data.zero_score_count}
                    </div>
                  </div>

                  <div className="border rounded p-3 bg-neutral-900 text-gray-100">
                    <div className="text-xs text-gray-400">失败平均耗时</div>
                    <div className="text-xl font-semibold">
                      {ragEvalFailureAnalysisQuery.data.average_failed_latency_ms === null
                        ? "-"
                        : `${ragEvalFailureAnalysisQuery.data.average_failed_latency_ms.toFixed(0)} ms`}
                    </div>
                  </div>
                </div>

                <details>
                  <summary className="cursor-pointer text-sm text-gray-300">
                    查看最近失败样例（
                    {ragEvalFailureAnalysisQuery.data.recent_failed_runs.length}）
                  </summary>

                  <div className="space-y-2 pt-2">
                    {ragEvalFailureAnalysisQuery.data.recent_failed_runs.length === 0 ? (
                      <div className="text-sm text-gray-500">
                        暂无失败样例。
                      </div>
                    ) : (
                      ragEvalFailureAnalysisQuery.data.recent_failed_runs.map((run) => (
                        <div
                          key={run.id}
                          className="border border-gray-700 rounded p-3 bg-black text-gray-100 space-y-2"
                        >
                          <div className="text-sm font-medium">
                            问题：{run.question}
                        </div>

                        <div className="text-xs text-gray-400">
                          Score：{run.score ?? "-"} ｜ 失败原因：
                          {run.failure_reasons.length > 0
                            ? run.failure_reasons.join("、")
                            : "无"}
                        </div>

                        <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                          {run.answer}
                        </pre>
                      </div>
                    ))
                  )}
                </div>
              </details>
            </div>
          ) : null}
        </div>

        <div className="border rounded p-4 space-y-3">
          <h3 className="text-base font-semibold">创建评测样例</h3>

          <input
            className="border rounded px-3 py-2 w-full"
            placeholder="评测问题，例如：用户登录状态应该怎么保存？"
            value={evalQuestion}
            onChange={(event) => setEvalQuestion(event.target.value)}
          />

          <input
            className="border rounded px-3 py-2 w-full"
            placeholder="预期关键词，用逗号分隔，例如：token, Authorization, JWT"
            value={evalKeywords}
            onChange={(event) => setEvalKeywords(event.target.value)}
          />

          <input
            className="border rounded px-3 py-2 w-full"
            placeholder="预期来源文件名，可选，例如：auth.md"
            value={evalSourceFilename}
            onChange={(event) => setEvalSourceFilename(event.target.value)}
          />

          <textarea
            className="border rounded px-3 py-2 w-full min-h-20"
            placeholder="备注，可选"
            value={evalNote}
            onChange={(event) => setEvalNote(event.target.value)}
          />

          <button
            className="border rounded px-4 py-2"
            onClick={handleCreateRagEvalCase}
            disabled={createRagEvalCaseMutation.isPending}
          >
            {createRagEvalCaseMutation.isPending ? "创建中..." : "创建评测样例"}
          </button>

          {createRagEvalCaseMutation.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              创建评测样例失败：
              {JSON.stringify(createRagEvalCaseMutation.error, null, 2)}
            </div>
          ) : null}
        </div>

        <div className="border rounded p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">评测样例列表</h3>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-eval-cases", knowledgeBaseId],
                })
              }
            >
              刷新样例
            </button>
          </div>

          {ragEvalCasesQuery.isLoading ? (
            <div className="text-sm text-gray-500">正在加载评测样例...</div>
          ) : null}

          {ragEvalCasesQuery.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              评测样例加载失败：
              {JSON.stringify(ragEvalCasesQuery.error, null, 2)}
            </div>
          ) : null}

          {ragEvalCasesQuery.data ? (
            <div className="space-y-3">
              <div className="text-sm text-gray-500">
                共 {ragEvalCasesQuery.data.count} 条评测样例。
              </div>

              {ragEvalCasesQuery.data.data.length === 0 ? (
                <div className="text-sm text-gray-500">
                  暂无评测样例。可以先在上方创建一个测试问题。
                </div>
              ) : (
                ragEvalCasesQuery.data.data.map((evalCase) => (
                  <div
                    key={evalCase.id}
                    className="border border-gray-700 rounded p-3 bg-neutral-900 text-gray-100 space-y-2"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium">
                        问题：{evalCase.question}
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          className="border rounded px-2 py-1 text-xs"
                          onClick={() => handleRunRagEvalCase(evalCase.id)}
                          disabled={runRagEvalCaseMutation.isPending}
                        >
                          {runRagEvalCaseMutation.isPending ? "运行中..." : "运行评测"}
                        </button>

                        <button
                          className="border border-red-500 text-red-400 rounded px-2 py-1 text-xs"
                          onClick={() => handleDeleteRagEvalCase(evalCase.id)}
                          disabled={deleteRagEvalCaseMutation.isPending}
                        >
                          删除
                        </button>
                      </div>
                    </div>

                    <div className="text-xs text-gray-400">
                      预期关键词：
                      {evalCase.expected_keywords.length > 0
                        ? evalCase.expected_keywords.join("、")
                        : "无"}{" "}
                      ｜ 预期来源：
                      {evalCase.expected_source_filename || "无"}
                    </div>

                    {evalCase.note ? (
                      <div className="text-xs text-gray-400">
                        备注：{evalCase.note}
                      </div>
                    ) : null}

                    {evalCase.created_at ? (
                      <div className="text-xs text-gray-500">
                        创建时间：{new Date(evalCase.created_at).toLocaleString()}
                      </div>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          ) : null}

          {runRagEvalCaseMutation.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              运行评测失败：
              {JSON.stringify(runRagEvalCaseMutation.error, null, 2)}
            </div>
          ) : null}

          {deleteRagEvalCaseMutation.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              删除评测样例失败：
              {JSON.stringify(deleteRagEvalCaseMutation.error, null, 2)}
            </div>
          ) : null}
        </div>

        <div className="border rounded p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">评测运行结果</h3>

            <button
              className="border rounded px-3 py-1 text-sm"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["rag-eval-runs", knowledgeBaseId],
                })
              }
            >
              刷新结果
            </button>
          </div>

          {ragEvalRunsQuery.isLoading ? (
            <div className="text-sm text-gray-500">正在加载评测结果...</div>
          ) : null}

          {ragEvalRunsQuery.isError ? (
            <div className="text-sm text-red-500 whitespace-pre-wrap">
              评测结果加载失败：
              {JSON.stringify(ragEvalRunsQuery.error, null, 2)}
            </div>
          ) : null}

          {ragEvalRunsQuery.data ? (
            <div className="space-y-3">
              <div className="text-sm text-gray-500">
                共 {ragEvalRunsQuery.data.count} 条评测运行结果。
              </div>

              {ragEvalRunsQuery.data.data.length === 0 ? (
                <div className="text-sm text-gray-500">
                  暂无评测结果。可以先点击某条样例的“运行评测”。
                </div>
              ) : (
                ragEvalRunsQuery.data.data.map((run) => (
                  <div
                    key={run.id}
                    className="border border-gray-700 rounded p-4 bg-neutral-900 text-gray-100 space-y-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium">问题：{run.question}</div>

                      <div className="text-xs text-gray-400">
                        Score：{run.score ?? "-"} ｜ 关键词命中：
                        {run.keyword_hit === null
                          ? "-"
                          : run.keyword_hit
                            ? "是"
                            : "否"}{" "}
                        ｜ 来源命中：
                        {run.source_hit === null
                          ? "-"
                          : run.source_hit
                            ? "是"
                            : "否"}{" "}
                        ｜ 耗时：{run.latency_ms ?? "-"} ms
                      </div>
                    </div>

                    <div className="text-xs text-gray-400">
                      预期关键词：
                      {run.expected_keywords.length > 0
                        ? run.expected_keywords.join("、")
                        : "无"}{" "}
                      ｜ 预期来源：
                      {run.expected_source_filename || "无"} ｜ 检索方式：
                      {run.retrieval_type}
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm font-medium text-gray-200">回答</div>
                      <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                        {run.answer}
                      </pre>
                    </div>

                    <details>
                      <summary className="cursor-pointer text-sm text-gray-300">
                        查看引用来源（{run.sources.length}）
                      </summary>

                      <div className="space-y-2 pt-2">
                        {run.sources.length === 0 ? (
                          <div className="text-sm text-gray-500">
                            当前评测结果没有引用来源。
                          </div>
                        ) : (
                          run.sources.map((source) => (
                            <div
                              key={source.chunk_id}
                              className="border border-gray-700 rounded p-3 bg-black text-gray-100 space-y-2"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <div className="text-sm font-medium">
                                  来源文件：{source.original_filename} ｜ Chunk{" "}
                                  {source.chunk_index}
                                </div>

                                <div className="text-xs text-gray-400">
                                  相似度：{source.similarity?.toFixed(4)} ｜ 关键词命中：
                                  {source.match_count} ｜ 长度：{source.content_length}
                                </div>
                              </div>

                              <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                                {source.content}
                              </pre>
                            </div>
                          ))
                        )}
                      </div>
                    </details>

                    <details>
                      <summary className="cursor-pointer text-sm text-gray-300">
                        查看执行过程 Trace
                      </summary>

                      <div className="pt-2 text-sm text-gray-400">
                        {run.trace.length > 0 ? run.trace.join(" → ") : "暂无 trace"}
                      </div>
                    </details>

                    {run.created_at ? (
                      <div className="text-xs text-gray-500">
                        创建时间：{new Date(run.created_at).toLocaleString()}
                      </div>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          ) : null}
        </div>
      </div>

      <div className="border rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-4">文档列表</h2>

        {documents.data.length === 0 ? (
          <div className="text-gray-500">该知识库下暂无文档</div>
        ) : (
          <div className="space-y-3">
            {documents.data.map((document) => {
              const isExpanded = expandedDocumentId === document.id

              return (
                <div key={document.id} className="border rounded p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">
                        {document.original_filename}
                      </div>

                      <div className="text-sm text-gray-500">
                        类型：{document.content_type || "未知"} ｜ 大小：
                        {formatFileSize(document.file_size)} ｜ 状态：
                        {document.status}
                      </div>

                      {document.error_message ? (
                        <div className="text-sm text-red-500">
                          解析信息：{document.error_message}
                        </div>
                      ) : null}

                      <div className="text-xs text-gray-400">
                        文档 ID：{document.id}
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <button
                        className="border rounded px-3 py-1"
                        onClick={() => handleToggleChunks(document.id)}
                      >
                        {isExpanded ? "收起切分结果" : "查看切分结果"}
                      </button>

                      <button
                        className="border rounded px-3 py-1"
                        onClick={() =>
                          handleDownload(document.id, document.original_filename)
                        }
                      >
                        下载
                      </button>

                      <button
                        className="border rounded px-3 py-1"
                        onClick={() => {
                          if (confirm("确定删除这个文档吗？")) {
                            deleteDocumentMutation.mutate(document.id)
                          }
                        }}
                        disabled={deleteDocumentMutation.isPending}
                      >
                        删除
                      </button>
                    </div>
                  </div>

                  {isExpanded ? (
                    <div className="border-t pt-4 space-y-3">
                      <div className="font-medium">切分结果</div>

                      {isChunksPending ? (
                        <div className="text-sm text-gray-500">
                          正在加载切分结果...
                        </div>
                      ) : null}

                      {isChunksError ? (
                        <div className="text-sm text-red-500">
                          切分结果加载失败
                        </div>
                      ) : null}

                      {!isChunksPending &&
                      !isChunksError &&
                      chunks?.data.length === 0 ? (
                        <div className="text-sm text-gray-500">
                          暂无切分结果。当前只有 txt、md 文件会自动生成切分结果。
                        </div>
                      ) : null}

                      {!isChunksPending &&
                      !isChunksError &&
                      chunks?.data.map((chunk) => (
                        <div
                          key={chunk.id}
                          className="border border-gray-700 rounded p-3 bg-neutral-900 text-gray-100 space-y-2"
                        >
                          <div className="flex items-center justify-between">
                            <div className="text-sm font-medium text-gray-100">
                              Chunk {chunk.chunk_index}
                            </div>

                            <div className="text-xs text-gray-400">
                              长度：{chunk.content_length}
                            </div>
                          </div>

                          <pre className="text-sm whitespace-pre-wrap break-words font-sans text-gray-100">
                            {chunk.content}
                          </pre>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}