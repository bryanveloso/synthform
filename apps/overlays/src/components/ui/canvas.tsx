import type { FC, PropsWithChildren } from "react";

export const Canvas: FC<PropsWithChildren> = ({ children }) => {
  return (
    <div className="relative aspect-video h-[1080px] w-[1920px] overflow-hidden">{children}</div>
  )
};
