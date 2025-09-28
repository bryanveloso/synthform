import { useEffect, useState } from 'react'

interface UseTimeOptions {
  interval?: number // Update interval in ms, default 1000
  format?: 'time' | 'datetime' | 'date' | 'custom' // What to return
  locale?: string // Locale for formatting (default 'en-US')
  hour12?: boolean // 12-hour format (true) or 24-hour (false)
  showSeconds?: boolean // Include seconds in time display
  customFormat?: (date: Date) => string // Custom formatting function
}

export function useTime(options: UseTimeOptions = {}) {
  const {
    interval = 1000,
    format = 'time',
    locale = 'en-US',
    hour12 = true,
    showSeconds = true,
    customFormat
  } = options

  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date())
    }, interval)

    return () => clearInterval(timer)
  }, [interval])

  // Format based on option
  const formatted = (() => {
    if (format === 'custom' && customFormat) {
      return customFormat(time)
    }

    const timeOptions: Intl.DateTimeFormatOptions = {
      hour: 'numeric',
      minute: '2-digit',
      ...(showSeconds && { second: '2-digit' }),
      hour12
    }

    switch (format) {
      case 'time':
        return time.toLocaleTimeString(locale, timeOptions)
      case 'date':
        return time.toLocaleDateString(locale)
      case 'datetime':
        return time.toLocaleString(locale, {
          ...timeOptions,
          year: 'numeric',
          month: 'short',
          day: 'numeric'
        })
      default:
        return time.toLocaleTimeString(locale, timeOptions)
    }
  })()

  // Pad single digits with zero
  const pad = (n: number) => n.toString().padStart(2, '0')

  return {
    // Raw values
    time,
    hours: time.getHours(),
    minutes: time.getMinutes(),
    seconds: time.getSeconds(),
    milliseconds: time.getMilliseconds(),

    // Formatted values
    formatted,
    hour12: time.getHours() % 12 || 12, // 12-hour format hour
    hourPadded: pad(time.getHours()),
    hour12Padded: pad(time.getHours() % 12 || 12),
    minutesPadded: pad(time.getMinutes()),
    secondsPadded: pad(time.getSeconds()),
    ampm: time.getHours() >= 12 ? 'PM' : 'AM',

    // Date values
    year: time.getFullYear(),
    month: time.getMonth() + 1, // 1-based
    day: time.getDate(),
    dayOfWeek: time.getDay(), // 0 = Sunday

    // Formatted date values
    monthName: time.toLocaleDateString(locale, { month: 'long' }),
    monthShort: time.toLocaleDateString(locale, { month: 'short' }),
    dayName: time.toLocaleDateString(locale, { weekday: 'long' }),
    dayShort: time.toLocaleDateString(locale, { weekday: 'short' }),
  }
}

// Convenience hook for just the date string
export function useCurrentDate(options?: Omit<UseTimeOptions, 'format'>) {
  const { formatted } = useTime({ ...options, format: 'date' })
  return formatted
}

// Convenience hook for just the time string
export function useCurrentTime(options?: Omit<UseTimeOptions, 'format'>) {
  const { formatted } = useTime({ ...options, format: 'time' })
  return formatted
}

// Hook for building custom time displays
export function useTimeComponents(options?: UseTimeOptions) {
  const data = useTime(options)

  return {
    ...data,
    // Override with formatted versions for display
    hours: data.hour12Padded,
    minutes: data.minutesPadded,
    seconds: data.secondsPadded,
    ampm: data.ampm,
    separator: ':',
  }
}
