// --- Auth ---

export interface UserResponse {
  id: string;
  username: string;
  display_name: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

// --- Reels ---

export interface ReelResponse {
  id: string;
  url: string;
  platform: string | null;
  status: string;
  thumbnail_url: string | null;
  created_at: string;
}

export interface ReelDetail extends ReelResponse {
  creator: string | null;
  caption: string | null;
  transcript: string | null;
  frame_description: string | null;
  ai_summary: string | null;
  ai_tags: string[] | null;
  content_type: string | null;
  mood: string | null;
  metadata_: Record<string, unknown> | null;
  updated_at: string | null;
}

export interface ReelListResponse {
  count: number;
  reels: ReelResponse[];
}

export interface ReelStatus {
  id: string;
  status: string;
  has_transcript: boolean;
  has_frame_description: boolean;
}

// --- Search ---

export interface SearchResult {
  post_id: string;
  url: string;
  platform: string | null;
  creator: string | null;
  caption: string | null;
  thumbnail_url: string | null;
  ai_summary: string | null;
  ai_tags: string[];
  score: number;
  matched_entities: string[];
}

export interface SearchResponse {
  query: string;
  count: number;
  results: SearchResult[];
}

// --- Entities ---

export interface EntityResponse {
  id: string;
  name: string;
  type: string;
  mention_count: number;
  created_at: string;
}

export interface EntityLinkedReel {
  post_id: string;
  url: string;
  platform: string | null;
  ai_summary: string | null;
  relationship: string | null;
  context: string | null;
}

export interface EntityWithReels extends EntityResponse {
  normalized_name: string;
  attributes: Record<string, unknown>;
  updated_at: string | null;
  linked_reels: EntityLinkedReel[];
}

export interface RelatedEntity {
  id: string;
  name: string;
  type: string;
  relation_type: string;
  strength: number;
}
