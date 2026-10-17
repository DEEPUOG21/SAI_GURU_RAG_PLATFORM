export type User = {
  id: string;
  email: string;
  role: "ADMIN" | "MANAGER" | "EMPLOYEE";
  tenant: string;
};
export type Document = {
  id: string;
  name: string;
  version: number;
  status: string;
  size: number;
  min_role: number;
  error: string | null;
  created_at: string;
  updated_at: string;
};
export type Source = {
  label: string;
  chunk_id: string | null;
  document_id: string | null;
  document: string;
  text: string;
  page: number | null;
  section: string;
  version: number | null;
  kind?: string;
  dense_score?: number | null;
  lexical_score?: number | null;
  rrf_score?: number;
  reranker_score?: number | null;
};
export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Source[];
  query_id?: string;
  grounding?: string;
};
export type Conversation = { id: string; title: string; created_at: string };
export type QuerySummary = {
  id: string;
  question: string;
  route: string;
  status: string;
  latency_ms: number | null;
  created_at: string;
};
export type Dashboard = {
  documents_indexed: number;
  total_queries: number;
  successful_queries: number;
  average_latency_ms: number | null;
  recent_documents: Document[];
  recent_queries: QuerySummary[];
  scope: string;
  generation_mode: string;
};
export type TraceStep = {
  node: string;
  status: string;
  latency_ms?: number;
  attempts?: number;
  output?: unknown;
  error?: string;
};
export type DebugQuery = {
  id: string;
  question: string;
  rewritten_query: string;
  route: string;
  status: string;
  grounding: string;
  answer: string;
  latency_ms: number | null;
  token_usage: Record<string, number> | null;
  estimated_cost: number | null;
  trace: TraceStep[];
  error: string | null;
  request_id: string;
  candidates: Source[];
};
export type Evaluation = {
  id: string;
  status: string;
  created_at: string;
  results: {
    aggregate?: Record<string, number>;
    delta?: Record<string, number>;
    methodology?: Record<string, string>;
    error?: string;
    baseline_id?: string;
    cases?: {
      question: string;
      answer: string;
      expected_answer: string;
      citations: Source[];
      metrics: Record<string, number>;
      token_usage: Record<string, number> | null;
      estimated_cost: number | null;
    }[];
  };
};
