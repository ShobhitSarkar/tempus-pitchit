export type ProductFitScores = {
  "xT CDx": number;
  xR: number;
  "xF+": number;
};

export type ScoreComponent = {
  label: string;
  value: number;
};

export type ProviderRanked = {
  provider_id: string;
  name: string;
  specialty: string;
  institution: string;
  city: string;
  state: string;
  region: string;
  monthly_patients: number;
  addressable_patients_per_month: number;
  pct_biomarker_tested: number | null;
  product_fit: ProductFitScores;
  best_fit_product: string;
  product_fit_reasons: Record<string, string[]>;
  products: string[];
  signal: string;
  fit_reasons: string[];
  crm: {
    has_crm_data: boolean;
    crm_score: number | null;
    top_objection: string | null;
    key_interest: string | null;
    reasoning: string | null;
  };
  score: number;
  score_components: ScoreComponent[];
};

export type CrmNote = {
  timestamp: string;
  author: string;
  text: string;
};

export type GenerationResponse = {
  objection_handler: {
    objection: string;
    response_bullets: string[];
  };
  meeting_script: {
    headline: string;
    bullets: string[];
    suggested_close: string;
  };
  likely_questions: Array<{
    question: string;
    intent: string;
    answerBullets: string[];
  }>;
};
