// ── Shared primitives ──────────────────────────────────────────────────────────

export type Priority = 'urgent' | 'important' | 'maybe' | 'skip';
export type DraftStatus = 'pending_review' | 'approved' | 'rejected' | 'copied' | 'superseded';
export type ConnectionStatus = 'active' | 'error' | 'revoked' | 'syncing' | 'pending';

export interface Participant {
  email: string;
  name: string | null;
  role: 'sender' | 'recipient' | 'cc' | 'bcc';
}

export interface ActionItem {
  description: string;
  due_date_hint: string | null;
  assignee_hint: string | null;
}

// ── Threads ────────────────────────────────────────────────────────────────────

export interface ThreadSummary {
  id: string;
  subject: string | null;
  snippet: string | null;
  last_message_at: string | null;
  is_unread: boolean;
  participants: Participant[];
  priority: Priority | null;
  summary: string | null;
  action_items: ActionItem[];
  requires_reply: boolean;
  draft_status: DraftStatus | null;
}

export interface ThreadListResponse {
  threads: ThreadSummary[];
  next_cursor: string | null;
}

export interface Message {
  id: string;
  platform_message_id: string;
  from_email: string;
  from_name: string | null;
  to_emails: string[];
  cc_emails: string[];
  subject: string | null;
  body_plain: string | null;
  snippet: string | null;
  internal_date: string;
  folder: string;
  labels: string[];
  is_sent_by_user: boolean;
  has_attachments: boolean;
}

export interface Analysis {
  id: string;
  priority: Priority;
  priority_confidence: number | null;
  summary: string;
  action_items: ActionItem[];
  requires_reply: boolean;
  sentiment: 'positive' | 'neutral' | 'negative' | 'mixed' | null;
}

export interface Draft {
  id: string;
  subject_line: string | null;
  body_plain: string;
  body_html: string | null;
  tone_used: string | null;
  status: DraftStatus;
  regeneration_count: number;
}

export interface ThreadDetail {
  id: string;
  subject: string | null;
  snippet: string | null;
  last_message_at: string | null;
  is_unread: boolean;
  participants: Participant[];
  messages: Message[];
  analysis: Analysis | null;
  draft: Draft | null;
}

// ── Drafts ─────────────────────────────────────────────────────────────────────

export interface DraftListItem extends Draft {
  thread_id: string;
  generated_at: string;
  reviewed_at: string | null;
}

export interface DraftUpdatePayload {
  status: 'approved' | 'rejected' | 'copied';
  user_edited_body?: string;
  feedback_note?: string;
}

// ── Connections ────────────────────────────────────────────────────────────────

export interface Connection {
  id: string;
  platform: string;
  platform_email: string | null;
  status: ConnectionStatus;
  last_synced_at: string | null;
  last_sync_error: string | null;
  granted_scopes: string[];
}

// ── Profile ────────────────────────────────────────────────────────────────────

export interface Profile {
  id: string;
  profile_version: number;
  voice_summary: string | null;
  tone_attributes: string[];
  attributes: {
    formality_score?: number;
    vocabulary_sample?: string[];
    topic_clusters?: Array<{ topic: string; frequency: number; keywords: string[] }>;
    greeting_patterns?: string[];
    sign_off_patterns?: string[];
    avg_email_length_words?: number;
  };
  messages_analyzed_count: number;
  analyzed_date_range_start: string | null;
  analyzed_date_range_end: string | null;
  model_id: string;
  generated_at: string;
}

// ── Auth ───────────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

// ── Jobs ───────────────────────────────────────────────────────────────────────

export interface Job {
  id: string;
  job_type: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'retrying';
  messages_processed: number;
  messages_total: number | null;
  error_message: string | null;
  triggered_by: string | null;
  queued_at: string;
  started_at: string | null;
  completed_at: string | null;
}
