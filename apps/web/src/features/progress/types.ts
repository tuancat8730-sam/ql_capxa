export type StageStatus = 'not_started' | 'in_progress' | 'done' | 'delayed' | 'blocked'
export type TaskStatus = 'todo' | 'doing' | 'done' | 'blocked'

export interface StagePlan {
  id: string
  package_id: string
  stage_code: string
  name: string
  planned_start: string | null
  planned_end: string | null
  actual_start: string | null
  actual_end: string | null
  progress_pct: number
  weight: number
  status: StageStatus
  effective_status: StageStatus
  notes: string | null
  task_count: number
  tasks_done: number
}

export interface Stages {
  package_progress: number
  current_stage: string
  stages: StagePlan[]
}

export interface Task {
  id: string
  package_id: string
  stage_plan_id: string | null
  title: string
  status: TaskStatus
  priority: 'low' | 'normal' | 'high'
  planned_end: string | null
  weight: number
  stage_all_done: boolean
}

export interface ProgressLog {
  id: string
  package_id: string
  log_date: string
  progress_pct: number
  summary: string | null
  issues: string | null
  next_steps: string | null
  workers: number | null
  weather: string | null
  author_name: string | null
  attachments: string[]
}

export interface TimelineStage {
  id: string
  stage_code: string
  name: string
  planned_start: string | null
  planned_end: string | null
  actual_start: string | null
  actual_end: string | null
  progress_pct: number
  effective_status: StageStatus
}

export interface TimelinePackage {
  id: string
  number: number
  name: string
  health: 'green' | 'amber' | 'red' | 'grey'
  progress_pct: number
  stages: TimelineStage[]
  contract: {
    contract_no: string
    start: string | null
    end: string | null
    end_date_override: boolean
    extended_end_date: string | null
  } | null
}

export interface Timeline {
  today: string
  range_start: string | null
  range_end: string | null
  packages: TimelinePackage[]
}

export const TASK_STATUSES: TaskStatus[] = ['todo', 'doing', 'done', 'blocked']
