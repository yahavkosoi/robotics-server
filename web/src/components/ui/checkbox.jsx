import { useEffect, useRef } from 'react'
import { cn } from '../../lib/utils'

export function Checkbox({ className, indeterminate = false, ...props }) {
  const ref = useRef(null)

  useEffect(() => {
    if (ref.current) {
      ref.current.indeterminate = Boolean(indeterminate)
    }
  }, [indeterminate])

  return <input ref={ref} type="checkbox" className={cn('checkbox', className)} {...props} />
}
