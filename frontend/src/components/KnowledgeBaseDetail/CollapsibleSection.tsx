import type { ReactNode } from "react"

type CollapsibleSectionProps = {
  title: string
  description?: string
  isOpen: boolean
  onToggle: () => void
  children: ReactNode
}

export const CollapsibleSection = ({
  title,
  description,
  isOpen,
  onToggle,
  children,
}: CollapsibleSectionProps) => {
  return (
    <div className="border rounded-lg p-4 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>

          {description ? (
            <p className="text-sm text-gray-500">{description}</p>
          ) : null}
        </div>

        <button
          type="button"
          className="border rounded px-3 py-1 text-sm whitespace-nowrap"
          onClick={onToggle}
        >
          {isOpen ? "收起" : "展开"}
        </button>
      </div>

      {isOpen ? <div className="space-y-4">{children}</div> : null}
    </div>
  )
}