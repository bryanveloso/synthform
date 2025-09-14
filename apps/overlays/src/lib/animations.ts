import { gsap } from 'gsap'

// Timeline item entrance - slides in from left
export const animateTimelineEntry = (element: HTMLElement, delay: number = 0) => {
  return gsap.fromTo(element,
    {
      x: -50,
      opacity: 0,
      scale: 0.95,
    },
    {
      x: 0,
      opacity: 1,
      scale: 1,
      duration: 0.5,
      delay,
      ease: 'power3.out',
    }
  )
}

// Timeline item exit - fades and slides out
export const animateTimelineExit = (element: HTMLElement) => {
  return gsap.to(element, {
    x: 50,
    opacity: 0,
    scale: 0.95,
    duration: 0.3,
    ease: 'power2.in',
  })
}

// Limit break bar fill animation
export const animateLimitBreakFill = (element: HTMLElement, targetWidth: number) => {
  return gsap.to(element, {
    width: `${targetWidth}%`,
    duration: 0.5,
    ease: 'power2.out',
  })
}

// Limit break bar "maxed" pulse
export const animateLimitBreakMaxed = (element: HTMLElement) => {
  return gsap.timeline({ repeat: -1 })
    .to(element, {
      scale: 1.05,
      duration: 0.5,
      ease: 'power2.inOut',
    })
    .to(element, {
      scale: 1,
      duration: 0.5,
      ease: 'power2.inOut',
    })
}

// Limit break execution flash
export const animateLimitBreakExecute = (container: HTMLElement) => {
  // Create flash overlay
  const flash = document.createElement('div')
  flash.style.position = 'absolute'
  flash.style.inset = '0'
  flash.style.backgroundColor = 'white'
  flash.style.pointerEvents = 'none'
  container.appendChild(flash)

  return gsap.timeline()
    .fromTo(flash,
      { opacity: 0 },
      { opacity: 0.8, duration: 0.1, ease: 'power2.in' }
    )
    .to(flash, { opacity: 0, duration: 0.3, ease: 'power2.out' })
    .call(() => flash.remove())
}

// Initial load animation for the entire overlay
export const animateOverlayEntrance = (container: HTMLElement) => {
  const tl = gsap.timeline()

  // Find different sections
  const limitbreak = container.querySelector('[data-limitbreak]')
  const timeline = container.querySelector('[data-timeline]')
  const music = container.querySelector('[data-music]')

  // Stagger the entrance of each section
  if (limitbreak) {
    tl.fromTo(limitbreak,
      { y: -20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.6, ease: 'power3.out' },
      0
    )
  }

  if (timeline) {
    tl.fromTo(timeline,
      { x: -30, opacity: 0 },
      { x: 0, opacity: 1, duration: 0.6, ease: 'power3.out' },
      0.1
    )
  }

  if (music) {
    tl.fromTo(music,
      { y: 20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.6, ease: 'power3.out' },
      0.2
    )
  }

  return tl
}

// Alert/notification style animation
export const animateAlert = (element: HTMLElement) => {
  return gsap.timeline()
    .fromTo(element,
      { scale: 0.8, opacity: 0 },
      { scale: 1.1, opacity: 1, duration: 0.2, ease: 'back.out(2)' }
    )
    .to(element, { scale: 1, duration: 0.2, ease: 'power2.out' })
}

// Shimmer effect for special events
export const animateShimmer = (element: HTMLElement) => {
  return gsap.to(element, {
    backgroundImage: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)',
    backgroundSize: '200% 100%',
    backgroundPosition: '200% 0',
    duration: 1.5,
    ease: 'power2.inOut',
  })
}

// Number count up animation
export const animateCount = (element: HTMLElement, from: number, to: number, duration: number = 0.5) => {
  return gsap.to({ value: from }, {
    value: to,
    duration,
    ease: 'power2.out',
    onUpdate: function() {
      element.textContent = Math.floor(this.targets()[0].value).toString()
    }
  })
}

// Simple entrance animation for individual components
export const animateComponentEntrance = (element: HTMLElement, direction: 'up' | 'down' | 'left' | 'right' = 'up') => {
  const from: any = { opacity: 0 }

  switch (direction) {
    case 'up':
      from.y = 20
      break
    case 'down':
      from.y = -20
      break
    case 'left':
      from.x = 20
      break
    case 'right':
      from.x = -20
      break
  }

  return gsap.fromTo(element, from, {
    x: 0,
    y: 0,
    opacity: 1,
    duration: 0.6,
    ease: 'power3.out'
  })
}