export type Alarm = { id: string; task_id: string; species: string; count: number; confidence: number; at: number; last_seen: number; hits: number; status: string; snapshot: string; video_time: number; frame_id: number; site: string }
export type Command = { id: string; alarm_id: string | null; duration: number; scenario: string; status: string; at: number; started_at: number | null; ended_at: number | null; message: string; mode?: 'acoustic' | 'infrared' | 'both' }
export type Event = { id: number; kind: string; ref_id: string; at: number; message: string }
export type Frame = { key: string; frame_id: number; video_time: number; duration: number; at: number; count: number; inference_ms: number; detections: { species: string; class_name: string; confidence: number; bbox: number[] }[] }
export type Preferences = { scenario: 'normal' | 'offline' | 'timeout'; confidence: number; consecutive: number; cooldown: number }
export type Me = { username: string; display_name: string; email: string | null; avatar: string | null; theme: 'b1bit' | 'tower' | 'signal' | 'pixel' }
export type Stats = {
  range_days: number
  trend: number[]
  species: { species: string; count: number }[]
  hourly: number[]
  breakdown: { new: number; processing: number; handled: number; ignored: number }
  exec: { total: number; completed: number; failed: number; avg_start_seconds: number | null; avg_done_seconds: number | null; dual_share: number | null }
}
export type State = {
  alarms: Alarm[]; commands: Command[]; events: Event[];
  counts: { total: number; pending: number; completed: number }; settings: Preferences;
  monitor: { status: string; task_id: string | null; message: string; frame: Frame | null; source: string; model: string; device: string; sample_fps: number; source_ready: boolean; model_ready: boolean; progress?: number; result_ready?: boolean; stream_ready?: boolean; video_id?: string };
  media_ticket: string; server_time: number;
}
