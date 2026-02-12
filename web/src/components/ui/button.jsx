import { cn } from '../../lib/utils'

export function Button({ className, variant = 'default', type = 'button', ...props }) {
  return <button type={type} className={cn('btn', `btn-${variant}`, className)} {...props} />
}
