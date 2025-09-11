import type { FC, PropsWithChildren } from "react";

export const Canvas: FC<PropsWithChildren> = ({ children }) => {
  return <div className="w-[1920px] h-[1080px] relative">{children}</div>;
};
