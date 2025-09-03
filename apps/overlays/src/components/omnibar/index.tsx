import { Alerts } from './alerts'
import { Base } from './base'
import { LimitBreak } from './limitbreak'
import { Timeline } from './timeline'

export const Omnibar = () => {
  return (
    <div>
      <Base />
      <Alerts />
      <LimitBreak />
      <Timeline />
    </div>
  )
}
