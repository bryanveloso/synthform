import { createFileRoute } from '@tanstack/react-router'
import { useACNHHunt, useACNHStats } from '@/hooks/use-questlog'
import type { ACNHEncounter } from '@/hooks/use-questlog'

export const Route = createFileRoute('/acnh/villager-hunt')({
  component: VillagerHuntOverlay,
})

function VillagerHuntOverlay() {
  const { data: huntData } = useACNHHunt()
  const { data: stats } = useACNHStats()
  const hunt = huntData?.hunt

  if (!hunt) {
    return null
  }

  return (
    <div className="flex h-screen w-screen flex-col justify-end">
      <div className="relative flex h-16 w-full items-center bg-shark-960">
        {/* Encounters — scrolls left, most recent first */}
        <div className="flex h-full items-center">
          {hunt.encounters.map((encounter, index) => (
            <EncounterItem
              key={encounter.id}
              encounter={encounter}
              isLatest={index === 0}
            />
          ))}
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Stats cluster */}
        <div className="flex h-full items-center">
          {hunt.target_villager && (
            <>
              <div className="h-6 w-px bg-shark-800" />
              <div className="flex items-center gap-2 px-4">
                <img
                  src={hunt.target_villager.icon_url}
                  alt={hunt.target_villager.name}
                  className="size-8 rounded-full"
                />
                <div className="flex flex-col">
                  <span className="font-caps text-xs text-shark-560">HUNTING FOR</span>
                  <span className="font-caps text-sm font-bold text-chalk">
                    {hunt.target_villager.name}
                  </span>
                </div>
              </div>
            </>
          )}

          <div className="h-6 w-px bg-shark-800" />
          <div className="flex flex-col items-center px-5">
            <span className="font-caps text-xs text-shark-560">ISLANDS</span>
            <span className="font-caps text-lg font-bold tabular-nums text-chalk">
              {hunt.encounter_count}
            </span>
          </div>

          {stats && (
            <>
              <div className="h-6 w-px bg-shark-800" />
              <div className="flex flex-col items-center px-5">
                <span className="font-caps text-xs text-shark-560">ALL-TIME</span>
                <span className="font-caps text-lg font-bold tabular-nums text-chalk">
                  {stats.total_islands}
                </span>
              </div>

              <div className="h-6 w-px bg-shark-800" />
              <div className="flex flex-col items-center px-5">
                <span className="font-caps text-xs text-shark-560">AVG/HUNT</span>
                <span className="font-caps text-lg font-bold tabular-nums text-chalk">
                  {stats.avg_islands_per_hunt}
                </span>
              </div>
            </>
          )}
        </div>

        {/* Decorative borders */}
        <div className="absolute top-0 h-1 w-full bg-[#040506]" />
        <div className="from-marigold to-lime absolute bottom-0 h-[1px] w-full bg-gradient-to-r" />
      </div>
    </div>
  )
}

function EncounterItem({
  encounter,
  isLatest,
}: {
  encounter: ACNHEncounter
  isLatest: boolean
}) {
  const { villager, recruited, encounters } = encounter

  return (
    <div
      className={`flex h-full items-center gap-2.5 border-r border-shark-800 px-4 ${
        recruited
          ? 'bg-lime/10'
          : isLatest
            ? 'bg-shark-920'
            : ''
      }`}
    >
      <img
        src={villager.icon_url}
        alt={villager.name}
        className="size-10 rounded-full"
      />
      <div className="flex flex-col">
        <div className="flex items-center gap-1.5">
          <span className="font-caps text-sm font-bold text-chalk">
            {villager.name}
          </span>
          {recruited && (
            <span className="rounded bg-lime/20 px-1 py-0.5 text-xs font-bold text-lime">
              RECRUITED
            </span>
          )}
        </div>
        <span className="text-xs text-shark-400">
          {villager.species} · {villager.personality}
          {encounters > 1 && ` · ${encounters}x`}
        </span>
      </div>
    </div>
  )
}
