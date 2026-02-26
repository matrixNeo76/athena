// ---------------------------------------------------------------------------
// ATHENA — shared TypeScript types (mirrors backend Pydantic schemas)
// ---------------------------------------------------------------------------

export type AnalysisType = 'company' | 'product' | 'market';

// ---- Pipeline stages -------------------------------------------------------
export type PipelineStage =
  | 'PENDING'
  | 'SCOUT'
  | 'ANALYST'
  | 'STRATEGY'
  | 'PRESENTER'
  | 'DONE'
  | 'ERROR';

// ---- REST request / response -----------------------------------------------
export interface StartRequest {
  target: string;
  type: AnalysisType;
}

export interface StartResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface StatusResponse {
  job_id: string;
  status: string;
  stage: PipelineStage;
  progress: number;
  message: string;
  started_at: string | null;
  completed_at: string | null;
  failed_at_stage: string | null;
  error_message: string | null;
}

// ---- Results ---------------------------------------------------------------
export interface DeckSlide {
  slide_number: number;
  title: string;
  subtitle?: string;
  bullets?: string[];
  speaker_note?: string;
}

export interface PresenterResult {
  job_id: string;
  target: string;
  report_markdown: string;
  deck_outline: DeckSlide[];
  report_path?: string;
  report_url?: string;
  presented_at?: string;   // FIX: was generated_at — matches backend PresenterResult.presented_at
}

export interface ResultsResponse {
  job_id: string;
  target: string;
  stage: PipelineStage;
  status: string;
  message: string;
  presenter_result: PresenterResult | null;
  swot?: Record<string, unknown> | null;
  gtm?: Record<string, unknown> | null;
  competitors?: string[] | null;
  key_trends?: string[] | null;
  report_url?: string | null;
  completed_at?: string | null;
}

// ---- WebSocket progress message --------------------------------------------
export interface WsProgressMessage {
  stage: PipelineStage;
  status: string;
  progress: number;
  message: string;
  timestamp: string;
}
