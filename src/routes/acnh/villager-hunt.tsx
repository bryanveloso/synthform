import { createFileRoute } from '@tanstack/react-router'
import { useACNHHunt } from '@/hooks/use-questlog'
import type { ACNHEncounter } from '@/hooks/use-questlog'

export const Route = createFileRoute('/acnh/villager-hunt')({
  component: VillagerHuntOverlay,
})

function VillagerHuntOverlay() {
  const { data } = useACNHHunt()
  const hunt = data?.hunt

  if (!hunt || hunt.encounters.length === 0) {
    return null
  }

  return (
    <div className="flex h-screen w-screen items-end justify-end p-8">
      <div className="flex flex-col gap-3">
        {/* Header with island count */}
        <div className="flex items-center justify-end gap-3">
          {hunt.target_villager && (
            <div className="flex items-center gap-2 rounded-lg bg-shark-950/80 px-3 py-1.5 backdrop-blur">
              <img
                src={hunt.target_villager.icon_url}
                alt={hunt.target_villager.name}
                className="size-6 rounded-full"
              />
              <span className="font-caps text-xs text-shark-400">
                Hunting for {hunt.target_villager.name}
              </span>
            </div>
          )}
          <div className="rounded-lg bg-shark-950/80 px-3 py-1.5 backdrop-blur">
            <span className="font-caps text-sm font-bold tabular-nums text-chalk">
              {hunt.encounter_count}
            </span>
            <span className="font-caps text-xs text-shark-400"> islands</span>
          </div>
        </div>

        {/* Encounter list */}
        {hunt.encounters.map((encounter, index) => (
          <EncounterCard
            key={encounter.id}
            encounter={encounter}
            isLatest={index === 0}
          />
        ))}
      </div>
    </div>
  )
}

function EncounterCard({
  encounter,
  isLatest,
}: {
  encounter: ACNHEncounter
  isLatest: boolean
}) {
  const { villager, recruited } = encounter

  return (
    <div
      className={`flex items-center gap-3 rounded-lg px-4 py-3 backdrop-blur transition-all ${
        recruited
          ? 'bg-lime/20 inset-ring inset-ring-lime/30'
          : isLatest
            ? 'bg-shark-950/90 inset-ring inset-ring-white/10'
            : 'bg-shark-950/70'
      }`}
    >
      <img
        src={villager.icon_url}
        alt={villager.name}
        className="size-12 rounded-full"
      />
      <div className="flex flex-col">
        <div className="flex items-center gap-2">
          <span className="font-caps text-sm font-bold text-chalk">
            {villager.name}
          </span>
          {recruited && (
            <span className="rounded bg-lime/20 px-1.5 py-0.5 text-xs font-bold text-lime">
              RECRUITED
            </span>
          )}
        </div>
        <span className="text-xs text-shark-400">
          {villager.species} · {villager.personality}
        </span>
      </div>
    </div>
  )
}
