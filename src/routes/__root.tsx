import { createRootRoute, Outlet } from '@tanstack/react-router'

import { ConnectionAlert } from '@/components/ui/connection-alert'

export const Route = createRootRoute({
  component: () => (
    <>
      <ConnectionAlert />
      <Outlet />
    </>
  ),
})
