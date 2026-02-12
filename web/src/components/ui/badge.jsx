import { cn } from '../../lib/utils'

export function Badge({ className, tone = 'neutral', ...props }) {
  return <span className={cn('badge', `badge-${tone}`, className)} {...props} />
}
