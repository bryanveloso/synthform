import type { FC } from 'react'

import { useCampaign } from '@/hooks/use-campaign'

import type { Milestone } from '@/types/campaign'

const Milestone: FC<{ next: Milestone }> = ({ next }) => {
  return (
    <div className="flex items-center gap-3">
      <div>
        <span className="font-caps text-shark-680">Next</span>
      </div>
      <div>
        <span className="font-sans font-bold">
          {next?.title} at {next?.threshold} subs
        </span>
      </div>
    </div>
  )
}

export const Campaign: FC = () => {
  const { campaign, totalSubs, nextMilestone, totalDuration,formatDurationDisplay } = useCampaign()

  return (
    <div className="relative overflow-x-hidden">
      <div className="flex items-center gap-3 pl-6 text-white">
        <div className="">
          <span className="font-caps from-lime to-marigold bg-linear-to-r bg-clip-text text-xl text-transparent">
            {campaign?.name}
          </span>
          <span className="ml-2 font-sans text-sm tabular-nums">
            {formatDurationDisplay(totalDuration)}
          </span>
        </div>
        <div className="font-sans tabular-nums">
          {totalSubs}/{nextMilestone?.threshold} subs
        </div>
        <Milestone next={nextMilestone!} />
      </div>
    </div>
  )
}
