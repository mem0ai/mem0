import React from 'react'
import { cn } from '@/lib/utils'
import {
  Clock9,
  CircleDotDashed,
  CircleCheck,
  CircleSlash,
} from 'lucide-react'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'

type EventStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'

interface StatusBadgeProps {
  status: EventStatus
  className?: string
  iconOnly?: boolean
}

export function StatusBadge({ status, className, iconOnly = false }: StatusBadgeProps) {
  const getStatusConfig = (status: EventStatus) => {
    switch (status) {
      case 'PENDING':
        return {
          label: 'Pending',
          icon: Clock9,
          className: 'text-onSurface-info-primary'
        }
      case 'RUNNING':
        return {
          label: 'Running',
          icon: CircleDotDashed,
          className: 'text-onSurface-info-primary'
        }
      case 'SUCCEEDED':
        return {
          label: 'Succeeded',
          icon: CircleCheck,
          className: 'text-onSurface-event-add'
        }
      case 'FAILED':
        return {
          label: 'Failed',
          icon: CircleSlash,
          className: 'text-onSurface-danger-primary'
        }
      default:
        return {
          label: 'Unknown',
          icon: Clock9,
          className: 'text-onSurface-default-secondary'
        }
    }
  }

  const config = getStatusConfig(status.toUpperCase() as EventStatus)
  const Icon = config.icon

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          className={cn(
            'flex h-4 w-4 items-center justify-center transition-colors',
            config.className,
            className
          )}
        >
          <Icon className="size-4" />
        </div>
      </TooltipTrigger>
      <TooltipContent side="bottom">
        {config.label}
      </TooltipContent>
    </Tooltip>
  )
}
