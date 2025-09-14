import { useMusic } from "@/hooks/use-music"
import type { FC } from "react"

export const Music: FC = () => {
  const { current, isPlaying, source, isConnected } = useMusic()

  return (
    <div>
      <div className="font-caps flex-1 text-center font-bold text-white">{source}</div>
      <div className="bg-shark-960 aspect-[39/22] h-[264px]">
        {current ? (
          <>
            <div>{current.title}</div>
            <div>{current.artist}</div>
            <div>{current.album}</div>
          </>
        ) : (
          <div>No music playing</div>
        )}
      </div>
    </div>
  )
}
