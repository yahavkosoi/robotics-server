import { useEffect, useMemo, useRef, useState } from 'react'

import { cn } from '../../lib/utils'

function normalize(text) {
  return String(text || '').toLowerCase()
}

export function SearchableSelect({
  value,
  onChange,
  options,
  placeholder = 'Select',
  searchPlaceholder = 'Search...',
  fixedOption,
  disabled = false,
  className
}) {
  const rootRef = useRef(null)
  const searchInputRef = useRef(null)
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [highlightedIndex, setHighlightedIndex] = useState(-1)

  const filteredOptions = useMemo(() => {
    const q = normalize(query).trim()
    if (!q) return options
    return options.filter((item) => normalize(item.label).includes(q))
  }, [options, query])

  const menuItems = useMemo(() => {
    const mapped = filteredOptions.map((item) => ({ kind: 'option', ...item }))
    if (fixedOption) {
      mapped.push({ kind: 'fixed', ...fixedOption })
    }
    return mapped
  }, [filteredOptions, fixedOption])

  const selectedLabel = useMemo(() => {
    const fromOptions = options.find((item) => item.value === value)
    if (fromOptions) return fromOptions.label
    if (fixedOption && fixedOption.value === value) return fixedOption.label
    return ''
  }, [fixedOption, options, value])

  useEffect(() => {
    if (!isOpen) return
    searchInputRef.current?.focus()
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return
    function handlePointerDown(event) {
      if (!rootRef.current?.contains(event.target)) {
        setIsOpen(false)
        setQuery('')
      }
    }
    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('touchstart', handlePointerDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('touchstart', handlePointerDown)
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return
    if (menuItems.length === 0) {
      setHighlightedIndex(-1)
      return
    }
    const selectedIndex = menuItems.findIndex((item) => item.value === value)
    setHighlightedIndex(selectedIndex >= 0 ? selectedIndex : 0)
  }, [isOpen, menuItems, value])

  useEffect(() => {
    if (!isOpen) return
    if (menuItems.length === 0) {
      setHighlightedIndex(-1)
      return
    }
    setHighlightedIndex((current) => {
      if (current < 0) return 0
      if (current >= menuItems.length) return menuItems.length - 1
      return current
    })
  }, [isOpen, menuItems.length])

  function closeMenu() {
    setIsOpen(false)
    setQuery('')
  }

  function openMenu() {
    if (disabled) return
    setIsOpen(true)
  }

  function selectItem(nextValue) {
    onChange(nextValue)
    closeMenu()
  }

  function moveHighlight(delta) {
    if (!menuItems.length) return
    setHighlightedIndex((current) => {
      if (current < 0) return 0
      const next = current + delta
      if (next < 0) return menuItems.length - 1
      if (next >= menuItems.length) return 0
      return next
    })
  }

  function handleKeyDown(event) {
    if (event.key === 'Escape') {
      if (isOpen) {
        event.preventDefault()
        closeMenu()
      }
      return
    }

    if (!isOpen && (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
      event.preventDefault()
      openMenu()
      return
    }

    if (!isOpen) return

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      moveHighlight(1)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      moveHighlight(-1)
      return
    }
    if (event.key === 'Enter') {
      if (highlightedIndex >= 0 && menuItems[highlightedIndex]) {
        event.preventDefault()
        selectItem(menuItems[highlightedIndex].value)
      }
    }
  }

  return (
    <div ref={rootRef} className={cn('searchable-select', className)} onKeyDown={handleKeyDown}>
      <button
        type="button"
        className="searchable-select-trigger"
        onClick={() => (isOpen ? closeMenu() : openMenu())}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        disabled={disabled}
      >
        <span className={selectedLabel ? '' : 'muted'}>{selectedLabel || placeholder}</span>
        <span className="searchable-select-caret" aria-hidden="true">
          {isOpen ? '▲' : '▼'}
        </span>
      </button>

      {isOpen ? (
        <div className="searchable-select-menu">
          <input
            ref={searchInputRef}
            className="searchable-select-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={searchPlaceholder}
          />
          <div className="searchable-select-options" role="listbox">
            {filteredOptions.length ? null : <div className="searchable-select-empty">No uploader names found</div>}
            {menuItems.map((item, index) => {
              const active = index === highlightedIndex
              const selected = item.value === value
              return (
                <button
                  key={`${item.kind}:${item.value}:${item.key || item.label}`}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={cn(
                    'searchable-select-option',
                    active && 'searchable-select-option-active',
                    selected && 'searchable-select-option-selected',
                    item.kind === 'fixed' && 'searchable-select-fixed'
                  )}
                  onMouseEnter={() => setHighlightedIndex(index)}
                  onClick={() => selectItem(item.value)}
                >
                  {item.label}
                </button>
              )
            })}
          </div>
        </div>
      ) : null}
    </div>
  )
}
