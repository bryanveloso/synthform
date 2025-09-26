import type { FC } from 'react'

import { Frame } from '@/components/ui/chyron'
import { useCampaign } from '@/hooks/use-campaign'
import type { Milestone } from '@/types/campaign'


const Milestone: FC<{ next: Milestone }> = ({ next }) => {
  return (
    <div className="inset-ring-shark-800 flex items-center rounded-sm bg-black inset-ring-1">
      <div className="from-shark-840 to-shark-880 inset-ring-shark-800 rounded-l-sm bg-gradient-to-b p-1 px-3 inset-ring">
        <span className="font-caps relative -top-0.25">Next</span>
      </div>
      <div className="p-1 px-3">
        <span className="font-sans font-bold">
          {next?.threshold}: {next?.title}
        </span>
      </div>
    </div>
  )
}

export const Campaign: FC = () => {
  const { campaign, totalSubsWithResubs, nextMilestone, totalDuration, formatDurationDisplay } =
    useCampaign()

  return (
    <Frame className="w-full">
      <div className="flex items-center gap-3 pl-6 text-white">
        {/* Campaign */}
        <div className="inset-ring-shark-800 flex items-center rounded-sm bg-black inset-ring-1">
          <div className="font-caps to-lime from-marigold bg-linear-to-r/longer bg-clip-text p-1 px-3 text-xl text-transparent">
            {campaign?.name}
          </div>
          <div className="border-l-shark-800 border-l p-1 px-3 font-sans text-sm font-bold tabular-nums">
            {formatDurationDisplay(totalDuration)}
          </div>
          <div className="border-l-shark-800 border-l p-1 px-3 font-sans text-sm font-bold tabular-nums">
            <span className="text-lime">
              {totalSubsWithResubs}/{nextMilestone?.threshold}
            </span>
            <span className="text-shark-560"> SUBS</span>
          </div>
        </div>

        {/* Milestones */}
        <Milestone next={nextMilestone!} />
      </div>
    </Frame>
  )
}
