import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import {
  KnowledgeBasesService,
  type KnowledgeBaseCreate,
  type KnowledgeBaseUpdate,
} from "@/client"

export const Route = createFileRoute("/_layout/knowledge-bases/")({
  component: KnowledgeBasesPage,
})

function KnowledgeBasesPage() {
  const queryClient = useQueryClient()

  const [name, setName] = useState("")
  const [description, setDescription] = useState("")

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState("")
  const [editingDescription, setEditingDescription] = useState("")

  const {
    data: knowledgeBases,
    isPending,
    isError,
  } = useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: () =>
      KnowledgeBasesService.readKnowledgeBases({
        skip: 0,
        limit: 100,
      }),
  })

  const createKnowledgeBaseMutation = useMutation({
    mutationFn: (data: KnowledgeBaseCreate) =>
      KnowledgeBasesService.createKnowledgeBase({
        requestBody: data,
      }),
    onSuccess: () => {
      setName("")
      setDescription("")
      queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] })
    },
  })

  const updateKnowledgeBaseMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: KnowledgeBaseUpdate
    }) =>
      KnowledgeBasesService.updateKnowledgeBase({
        id,
        requestBody: data,
      }),
    onSuccess: () => {
      setEditingId(null)
      setEditingName("")
      setEditingDescription("")
      queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] })
    },
  })

  const deleteKnowledgeBaseMutation = useMutation({
    mutationFn: (id: string) =>
      KnowledgeBasesService.deleteKnowledgeBase({
        id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] })
    },
  })

  const handleCreate = () => {
    if (!name.trim()) {
      alert("知识库名称不能为空")
      return
    }

    createKnowledgeBaseMutation.mutate({
      name: name.trim(),
      description: description.trim() || null,
    })
  }

  const startEdit = (knowledgeBase: {
    id: string
    name: string
    description?: string | null
  }) => {
    setEditingId(knowledgeBase.id)
    setEditingName(knowledgeBase.name)
    setEditingDescription(knowledgeBase.description || "")
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditingName("")
    setEditingDescription("")
  }

  const handleSaveEdit = () => {
    if (!editingId) {
      return
    }

    if (!editingName.trim()) {
      alert("知识库名称不能为空")
      return
    }

    updateKnowledgeBaseMutation.mutate({
      id: editingId,
      data: {
        name: editingName.trim(),
        description: editingDescription.trim() || null,
      },
    })
  }

  if (isPending) {
    return <div className="p-6">正在加载知识库...</div>
  }

  if (isError) {
    return <div className="p-6">知识库加载失败</div>
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">知识库管理</h1>
        <p className="text-sm text-gray-500">
          在这里创建和管理你的知识库，后续可以在知识库中上传文档。
        </p>
      </div>

      <div className="border rounded-lg p-4 space-y-3">
        <h2 className="text-lg font-semibold">创建知识库</h2>

        <div className="space-y-2">
          <input
            className="border rounded px-3 py-2 w-full"
            placeholder="请输入知识库名称"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />

          <textarea
            className="border rounded px-3 py-2 w-full"
            placeholder="请输入知识库描述，可选"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />

          <button
            className="border rounded px-4 py-2"
            onClick={handleCreate}
            disabled={createKnowledgeBaseMutation.isPending}
          >
            {createKnowledgeBaseMutation.isPending ? "创建中..." : "创建知识库"}
          </button>
        </div>
      </div>

      <div className="border rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-4">我的知识库</h2>

        {knowledgeBases?.data.length === 0 ? (
          <div className="text-gray-500">暂无知识库</div>
        ) : (
          <div className="space-y-3">
            {knowledgeBases?.data.map((knowledgeBase) => (
              <div key={knowledgeBase.id} className="border rounded p-4">
                {editingId === knowledgeBase.id ? (
                  <div className="space-y-3">
                    <input
                      className="border rounded px-3 py-2 w-full"
                      value={editingName}
                      onChange={(event) => setEditingName(event.target.value)}
                      placeholder="请输入知识库名称"
                    />

                    <textarea
                      className="border rounded px-3 py-2 w-full"
                      value={editingDescription}
                      onChange={(event) =>
                        setEditingDescription(event.target.value)
                      }
                      placeholder="请输入知识库描述，可选"
                    />

                    <div className="flex gap-2">
                      <button
                        className="border rounded px-3 py-1"
                        onClick={handleSaveEdit}
                        disabled={updateKnowledgeBaseMutation.isPending}
                      >
                        {updateKnowledgeBaseMutation.isPending
                          ? "保存中..."
                          : "保存"}
                      </button>

                      <button
                        className="border rounded px-3 py-1"
                        onClick={cancelEdit}
                        disabled={updateKnowledgeBaseMutation.isPending}
                      >
                        取消
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{knowledgeBase.name}</div>
                      <div className="text-sm text-gray-500">
                        {knowledgeBase.description || "暂无描述"}
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <Link
                        className="border rounded px-3 py-1"
                        to="/knowledge-bases/$knowledgeBaseId"
                        params={{ knowledgeBaseId: knowledgeBase.id }}
                      >
                        进入
                      </Link>

                      <button
                        className="border rounded px-3 py-1"
                        onClick={() => startEdit(knowledgeBase)}
                      >
                        编辑
                      </button>

                      <button
                        className="border rounded px-3 py-1"
                        onClick={() => {
                          if (confirm("确定删除这个知识库吗？")) {
                            deleteKnowledgeBaseMutation.mutate(knowledgeBase.id)
                          }
                        }}
                        disabled={deleteKnowledgeBaseMutation.isPending}
                      >
                        删除
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}