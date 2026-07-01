import type { CrmNote, GenerationResponse, ProviderRanked } from "./types";

const baseUrl = "/api";

export async function getRankedProviders(
  weights?: { w_volume?: number; w_fit?: number; w_engagement?: number },
): Promise<ProviderRanked[]> {
  const params = new URLSearchParams();
  if (weights?.w_volume != null) params.set("w_volume", String(weights.w_volume));
  if (weights?.w_fit != null) params.set("w_fit", String(weights.w_fit));
  if (weights?.w_engagement != null) params.set("w_engagement", String(weights.w_engagement));
  const url = `${baseUrl}/providers/ranked${params.toString() ? `?${params.toString()}` : ""}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Unable to load providers: ${response.statusText}`);
  }
  return response.json();
}

export async function generateBrief(providerId: string): Promise<GenerationResponse> {
  const response = await fetch(`${baseUrl}/providers/${encodeURIComponent(providerId)}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Unable to generate brief: ${response.statusText}`);
  }
  return response.json();
}

export async function getNotes(providerId: string): Promise<CrmNote[]> {
  const response = await fetch(`${baseUrl}/providers/${encodeURIComponent(providerId)}/notes`);
  if (!response.ok) {
    throw new Error(`Unable to load notes: ${response.statusText}`);
  }
  return (await response.json()).notes;
}

export async function addNote(providerId: string, text: string): Promise<CrmNote[]> {
  const response = await fetch(`${baseUrl}/providers/${encodeURIComponent(providerId)}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) {
    throw new Error(`Unable to save note: ${response.statusText}`);
  }
  return (await response.json()).notes;
}
