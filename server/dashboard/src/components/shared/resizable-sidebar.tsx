"use client"

import {
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { Button } from "@/components/ui/button"
import { ChevronDown, ChevronUp, X } from "lucide-react"
import { cn } from "@/lib/utils"

export type SidebarTab = {
  id: string
  label: string
  content: ReactNode
}

interface ResizableSidebarProps {
  isOpen: boolean
  title?: ReactNode
  badge?: ReactNode
  onClose: () => void
  onNavigateUp?: () => void
  onNavigateDown?: () => void
  tabs?: SidebarTab[]
  defaultTabId?: string
  onTabChange?: (tabId: string) => void
  headerActions?: ReactNode
  children?: ReactNode
  initialWidth?: number
  minWidth?: number
  maxWidth?: number
  className?: string
  overlay?: boolean
  enableKeyboardNavigation?: boolean
}

const DEFAULT_WIDTH = 720
const DEFAULT_MIN_WIDTH = 360
const DEFAULT_MAX_RATIO = 0.85

export function ResizableSidebar({
  isOpen,
  title,
  badge,
  onClose,
  onNavigateUp,
  onNavigateDown,
  tabs,
  defaultTabId,
  onTabChange,
  headerActions,
  children,
  initialWidth = DEFAULT_WIDTH,
  minWidth = DEFAULT_MIN_WIDTH,
  maxWidth,
  className,
  overlay = false,
  enableKeyboardNavigation = true,
}: ResizableSidebarProps) {
  const [width, setWidth] = useState(initialWidth)
  const [activeTabId, setActiveTabId] = useState<string | undefined>(
    defaultTabId
  )
  const isResizingRef = useRef(false)
  const sidebarRef = useRef<HTMLDivElement>(null)

  const tabsList = useMemo(() => tabs ?? [], [tabs])

  useEffect(() => {
    if (!tabsList.length) return

    setActiveTabId((prev) => {
      if (prev && tabsList.some((tab) => tab.id === prev)) {
        return prev
      }
      return defaultTabId ?? tabsList[0]?.id
    })
  }, [tabsList, defaultTabId])

  const resolveMaxWidth = useCallback(() => {
    if (maxWidth) return maxWidth
    if (typeof window === "undefined") return DEFAULT_WIDTH
    return Math.max(minWidth, window.innerWidth * DEFAULT_MAX_RATIO)
  }, [maxWidth, minWidth])

  const handleMouseDown = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault()
    isResizingRef.current = true
  }, [])

  // Keyboard navigation - listen at window level when drawer is open
  useEffect(() => {
    if (!isOpen || !enableKeyboardNavigation) return

    const handleKeyDown = (event: KeyboardEvent) => {
      // Only handle arrow keys
      if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return

      // Only handle if no input/textarea/select is focused
      const activeElement = document.activeElement
      const tagName = activeElement?.tagName.toLowerCase()

      // Skip if user is typing in an input field
      if (
        tagName === "input" ||
        tagName === "textarea" ||
        tagName === "select" ||
        (activeElement as HTMLElement)?.isContentEditable
      ) {
        return
      }

      // Handle arrow up
      if (event.key === "ArrowUp") {
        if (onNavigateUp) {
          event.preventDefault()
          event.stopPropagation()
          onNavigateUp()
        }
      }

      // Handle arrow down
      if (event.key === "ArrowDown") {
        if (onNavigateDown) {
          event.preventDefault()
          event.stopPropagation()
          onNavigateDown()
        }
      }
    }

    // Add listener to window with capture phase
    window.addEventListener("keydown", handleKeyDown, { capture: true })

    return () => {
      window.removeEventListener("keydown", handleKeyDown, { capture: true })
    }
  }, [isOpen, enableKeyboardNavigation, onNavigateUp, onNavigateDown])

  useEffect(() => {
    if (!isOpen) {
      isResizingRef.current = false
      return
    }

    const handleMouseMove = (event: MouseEvent) => {
      if (!isResizingRef.current) return

      const viewportWidth = typeof window !== "undefined" ? window.innerWidth : undefined
      const allowedMaxWidth = resolveMaxWidth()
      const newWidth = viewportWidth ? viewportWidth - event.clientX : width

      if (newWidth >= minWidth && newWidth <= allowedMaxWidth) {
        setWidth(newWidth)
      } else if (newWidth < minWidth) {
        setWidth(minWidth)
      } else if (newWidth > allowedMaxWidth) {
        setWidth(allowedMaxWidth)
      }
    }

    const handleMouseUp = () => {
      isResizingRef.current = false
    }

    document.addEventListener("mousemove", handleMouseMove)
    document.addEventListener("mouseup", handleMouseUp)

    return () => {
      document.removeEventListener("mousemove", handleMouseMove)
      document.removeEventListener("mouseup", handleMouseUp)
    }
  }, [
    isOpen,
    resolveMaxWidth,
    minWidth,
    width,
  ])

  useEffect(() => {
    if (!isOpen) {
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
      return
    }

    if (isResizingRef.current) {
      document.body.style.cursor = "col-resize"
      document.body.style.userSelect = "none"
    } else {
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }

    return () => {
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }
  }, [isOpen, width])

  const handleTabClick = useCallback(
    (tabId: string) => {
      setActiveTabId(tabId)
      onTabChange?.(tabId)
    },
    [onTabChange]
  )

  const renderTabs = () => {
    if (!tabsList.length) {
      return <div className="flex-1 overflow-y-auto">{children}</div>
    }

    return (
      <>
        <div className="flex border-b border-memBorder-primary shrink-0">
          {tabsList.map((tab) => {
            const isActive = tab.id === activeTabId
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => handleTabClick(tab.id)}
                className={cn(
                  "px-3 py-2 typo-body-xs border-b-2 transition-colors flex-1",
                  isActive
                    ? "border-onSurface-default-primary text-onSurface-default-primary"
                    : "border-transparent text-onSurface-default-secondary hover:text-onSurface-default-primary"
                )}
              >
                {tab.label}
              </button>
            )
          })}
        </div>

        <div className="flex-1 overflow-y-auto">
          {tabsList.map((tab) => (
            <div
              key={tab.id}
              className={cn(activeTabId === tab.id ? "block" : "hidden")}
            >
              {tab.content}
            </div>
          ))}
        </div>
      </>
    )
  }

  return (
    <>
      {overlay && (
        <div
          className={cn(
            "fixed inset-0 z-40 bg-black/30 transition-opacity duration-300 ease-out",
            isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
          )}
          style={{ top: 0, bottom: 0, left: 0, right: 0, marginTop: 0 }}
          onClick={onClose}
          onKeyDown={(e) => e.stopPropagation()}
        />
      )}
      <div
        ref={sidebarRef}
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex h-full flex-col bg-surface-default-primary border-l border-memBorder-primary shadow-xl transition-transform duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]",
          isOpen ? "translate-x-0" : "translate-x-full",
          className
        )}
        style={{ width, top: 0, bottom: 0, marginTop: 0 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="absolute left-0 top-0 z-50 h-full w-1 cursor-col-resize transition-all duration-200 hover:w-2 hover:bg-blue-500/30"
          onMouseDown={handleMouseDown}
        >
          <div className="absolute left-0 top-0 h-full w-2 -translate-x-1" />
        </div>
        <div className="flex items-center justify-between border-b border-memBorder-primary px-3 pb-2 pt-3">
          <div className="flex items-center gap-3">
            {title ? (
              <span className="text-lg font-semibold text-onSurface-default-primary">
                {title}
              </span>
            ) : null}
            {badge}
          </div>
          <div className="flex items-center gap-2">
            {headerActions}
            <Button
              variant="ghost"
              size="icon"
              className="size-6 text-onSurface-default-primary hover:text-onSurface-default-secondary dark:hover:text-gray-300 disabled:text-gray-400 dark:disabled:text-gray-600"
              onClick={onNavigateUp}
              disabled={!onNavigateUp}
            >
              <ChevronUp className="size-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-6 text-onSurface-default-primary hover:text-onSurface-default-secondary dark:hover:text-gray-300 disabled:text-gray-400 dark:disabled:text-gray-600"
              onClick={onNavigateDown}
              disabled={!onNavigateDown}
            >
              <ChevronDown className="size-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-6 text-onSurface-default-primary hover:text-onSurface-default-secondary dark:hover:text-gray-300"
              onClick={onClose}
            >
              <X className="size-4" />
            </Button>
          </div>
        </div>
        {renderTabs()}
      </div>
    </>
  )
}

export default ResizableSidebar
