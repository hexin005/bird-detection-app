export type Alarm = { id: string; task_id: string; species: string; count: number; confidence: number; at: number; last_seen: number; hits: number; status: string; snapshot: string; video_time: number; frame_id: number; site: string }
export type Command = { id: string; alarm_id: string | null; duration: number; scenario: string; status: string; at: number; started_at: number | null; ended_at: number | null; message: string; mode?: 'acoustic' | 'infrared' | 'both' }
export type Event = { id: number; kind: string; ref_id: string; at: number; message: string }
export type Frame = { key: string; frame_id: number; video_time: number; duration: number; at: number; count: number; inference_ms: number; detections: { species: string; class_name: string; confidence: number; bbox: number[] }[] }
export type Preferences = { scenario: 'normal' | 'offline' | 'timeout'; confidence: number; consecutive: number; cooldown: number }
export type AutoRule = { id: number; user_id: number; name: string; trigger: 'alarm_any' | 'alarm_burst'; mode: 'acoustic' | 'infrared' | 'both'; duration: number; cooldown_minutes: number; enabled: number; last_fired_at: number | null; created_at: number }
export type Patrol = { user_id: number; enabled: number; start_minute: number; end_minute: number; interval_minutes: number; mode: 'acoustic' | 'infrared' | 'both'; duration: number; last_fired_at: number | null }
export type Me = { username: string; display_name: string; email: string | null; avatar: string | null; theme: 'b1bit' | 'tower' | 'signal' | 'pixel' }
export type Stats = {
  range_days: number
  dates: string[]
  trend: number[]
  task_trend: number[]
  bird_trend: number[]
  bird_species: { species: string; count: number }[]
  species: { species: string; count: number }[]
  hourly: number[]
  breakdown: { new: number; processing: number; handled: number; ignored: number }
  exec: { total: number; completed: number; failed: number; avg_start_seconds: number | null; avg_done_seconds: number | null; dual_share: number | null }
}
export type LibrarySpecies = { species: string; first_seen: number; last_seen: number; peak_count: number }
export type LibraryItem = { id: string; name: string; status: string; at: number; ended_at: number | null; message: string; duration: number; progress: number; result_ready: number; video_id: string; species: LibrarySpecies[] }
export type LibrarySummary = { tasks_total: number; birds_total: number; today_tasks: number; today_birds: number }
export type LibraryDetail = LibraryItem & { intervals: { species: string; start: number; end: number; peak_count: number }[]; alarms: Alarm[]; stream_ready?: boolean }
export type State = {
  alarms: Alarm[]; commands: Command[]; events: Event[];
  counts: { total: number; pending: number; completed: number }; settings: Preferences;
  monitor: { status: string; task_id: string | null; message: string; frame: Frame | null; source: string; model: string; device: string; sample_fps: number; source_ready: boolean; model_ready: boolean; progress?: number; result_ready?: boolean; stream_ready?: boolean; video_id?: string };
  media_ticket: string; server_time: number;
}

// ===== 鸟类知识库(/api/knowledge,种子见 backend/knowledge.py) =====
export type SpeciesRecords = {
  total: number; pending: number; last_seen: number | null;
  cover: string | null; best_confidence: number | null;
  videos: number; peak_count: number; first_seen: number | null;
  hour_buckets: number[]; // 全历史告警按本地时间一天 0-23 时聚合
}
export type SpeciesKnowledge = {
  name: string; en: string;
  scientific_name: string | null; family: string | null;
  domestic_protection: string | null; iucn_status: string | null;
  level: 'high' | 'mid' | 'low';
  desc: string; harm: string; traits: string; hours: string; advice: string;
  voice?: string | null; diet?: string | null; ecology?: string | null;
  records: SpeciesRecords;
}
// api=接口数据;fallback=请求失败回落内置静态数据,此时本园统计不可用(不得当 0 展示)
export type KnowledgeSource = 'loading' | 'api' | 'fallback'
