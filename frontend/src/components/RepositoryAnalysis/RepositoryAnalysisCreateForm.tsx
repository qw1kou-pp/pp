import { zodResolver } from "@hookform/resolvers/zod"
import {
  useMutation,
  useQueryClient,
} from "@tanstack/react-query"
import { Github } from "lucide-react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type {
  RepositoryAnalysisTaskCreate,
  RepositoryAnalysisTaskPublic,
} from "@/client"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"

import {
  createRepositoryAnalysisTask,
  repositoryAnalysisKeys,
  syncRepositoryAnalysisTaskToLists,
} from "./repositoryAnalysisQueries"
import {
  formatRepositoryAnalysisError,
} from "./repositoryAnalysisUi"

const repositoryAnalysisFormSchema =
  z.object({
    repository_url: z
      .string()
      .trim()
      .min(
        1,
        "请输入 GitHub 仓库地址",
      )
      .refine(
        isPublicGitHubRepositoryUrl,
        "请输入公开 GitHub 仓库地址，例如 https://github.com/owner/repository",
      ),

    report_language: z.enum([
      "zh-CN",
      "en-US",
    ]),
  })

type RepositoryAnalysisFormData =
  z.infer<
    typeof repositoryAnalysisFormSchema
  >

type RepositoryAnalysisCreateFormProps = {
  onCreated: (
    task: RepositoryAnalysisTaskPublic,
  ) => void
}

export function RepositoryAnalysisCreateForm({
  onCreated,
}: RepositoryAnalysisCreateFormProps) {
  const queryClient =
    useQueryClient()

  const {
    showSuccessToast,
    showErrorToast,
  } = useCustomToast()

  const form =
    useForm<RepositoryAnalysisFormData>({
      resolver: zodResolver(
        repositoryAnalysisFormSchema,
      ),
      mode: "onBlur",
      defaultValues: {
        repository_url: "",
        report_language: "zh-CN",
      },
    })

  const mutation = useMutation({
    mutationFn: (
      request: RepositoryAnalysisTaskCreate,
    ) =>
      createRepositoryAnalysisTask(
        request,
      ),

    onSuccess: (task) => {
      queryClient.setQueryData(
        repositoryAnalysisKeys.detail(
          task.id,
        ),
        task,
      )

      syncRepositoryAnalysisTaskToLists(
        queryClient,
        task,
      )

      void queryClient.invalidateQueries({
        queryKey:
          repositoryAnalysisKeys.lists(),
      })

      const selectedLanguage =
        form.getValues(
          "report_language",
        )

      form.reset({
        repository_url: "",
        report_language:
          selectedLanguage,
      })

      showSuccessToast(
        "仓库分析任务已创建",
      )

      onCreated(task)
    },

    onError: (error) => {
      showErrorToast(
        formatRepositoryAnalysisError(
          error,
        ),
      )
    },
  })

  const onSubmit = (
    values: RepositoryAnalysisFormData,
  ) => {
    mutation.mutate({
      repository_url:
        values.repository_url.trim(),
      report_language:
        values.report_language,
    })
  }

  return (
    <Card className="gap-4">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Github className="size-5" />
          提交仓库
        </CardTitle>

        <CardDescription>
          输入公开 GitHub 仓库地址。任务将在后台下载固定
          Commit，并生成仓库分析报告。
        </CardDescription>
      </CardHeader>

      <CardContent>
        <Form {...form}>
          <form
            className="grid gap-4 md:grid-cols-[minmax(0,1fr)_11rem_auto]"
            onSubmit={
              form.handleSubmit(
                onSubmit,
              )
            }
          >
            <FormField
              control={form.control}
              name="repository_url"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    GitHub 仓库地址
                  </FormLabel>

                  <FormControl>
                    <Input
                      placeholder="https://github.com/owner/repository"
                      autoComplete="url"
                      disabled={
                        mutation.isPending
                      }
                      {...field}
                    />
                  </FormControl>

                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="report_language"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    报告语言
                  </FormLabel>

                  <Select
                    value={field.value}
                    onValueChange={
                      field.onChange
                    }
                    disabled={
                      mutation.isPending
                    }
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>

                    <SelectContent>
                      <SelectItem value="zh-CN">
                        中文
                      </SelectItem>

                      <SelectItem value="en-US">
                        English
                      </SelectItem>
                    </SelectContent>
                  </Select>

                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="flex items-start pt-8">
              <LoadingButton
                type="submit"
                className="w-full md:w-auto"
                loading={
                  mutation.isPending
                }
              >
                <Github />
                {mutation.isPending
                  ? "创建中"
                  : "开始分析"}
              </LoadingButton>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}

function isPublicGitHubRepositoryUrl(
  value: string,
): boolean {
  try {
    const url = new URL(
      value.trim(),
    )

    if (
      url.protocol !== "https:" ||
      url.hostname.toLowerCase() !==
        "github.com"
    ) {
      return false
    }

    const pathParts =
      url.pathname
        .split("/")
        .filter(Boolean)

    return pathParts.length === 2
  } catch {
    return false
  }
}