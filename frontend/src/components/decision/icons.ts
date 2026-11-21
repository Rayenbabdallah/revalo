import { Recycle, Repeat2, Tag, type LucideIcon } from 'lucide-react'

import type { DecisionAction } from '../../lib/api'

export const ACTION_ICON: Record<DecisionAction, LucideIcon> = {
  reuse: Repeat2,
  sell: Tag,
  recycle: Recycle,
}
