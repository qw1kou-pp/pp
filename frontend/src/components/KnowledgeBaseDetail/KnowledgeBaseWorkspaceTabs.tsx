import {
  WORKSPACE_TABS,
  type WorkspaceTab,
} from "./knowledgeBaseDetailTypes"

type KnowledgeBaseWorkspaceTabsProps = {
  activeTab: WorkspaceTab
  onTabChange: (tab: WorkspaceTab) => void
}

export function KnowledgeBaseWorkspaceTabs({
  activeTab,
  onTabChange,
}: KnowledgeBaseWorkspaceTabsProps) {
  return (
    <nav
      className="sticky top-2 z-20 rounded-2xl border border-slate-600 bg-white/95 p-2 shadow-sm backdrop-blur"
      aria-label="知识库工作区"
    >
      <div
        className="grid grid-cols-2 gap-2 lg:grid-cols-4"
        role="tablist"
      >
        {WORKSPACE_TABS.map((tab) => {
          const isActive = activeTab === tab.key

          return (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => onTabChange(tab.key)}
              className={`rounded-xl px-3 py-3 text-left transition ${
                isActive
                  ? "bg-sky-600 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              <div className="text-sm font-medium">{tab.label}</div>

              <div
                className={`mt-1 hidden text-xs leading-5 md:block ${
                  isActive ? "text-sky-100" : "text-slate-400"
                }`}
              >
                {tab.description}
              </div>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
