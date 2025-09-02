import { Alerts } from './alerts'
import { Base } from './base'
import { Timeline } from './timeline'

export const Omnibar = () => {
  return (
    <div>
      <Base />
      <Alerts />
      <Timeline />
    </div>
  )
}
