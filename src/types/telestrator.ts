export interface TelestratorPoint {
  x: number // 0–1 normalized
  y: number // 0–1 normalized
}

export interface TelestratorDrawData {
  id: string
  points: TelestratorPoint[]
  color: string
  width: number
  done: boolean
}
