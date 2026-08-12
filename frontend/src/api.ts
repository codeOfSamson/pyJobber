const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string;

export interface RunStat {
  run_date: string;
  search_term_used: string | null;
  total_applied: number;
  total_failed: number;
  total_skipped: number;
}

export async function fetchStats(): Promise<RunStat[]> {
  const response = await fetch(`${API_BASE_URL}/api/stats`);
  if (!response.ok) {
    throw new Error(`Failed to fetch stats: ${response.status}`);
  }
  return response.json();
}

export interface Application {
  id: number;
  url: string;
  site: string;
  search_term: string | null;
  status: string;
  applied_at: string | null;
  error_message: string | null;
  needs_review: boolean;
  reviewed: boolean;
}

export interface ApplicationFilters {
  site?: string;
  status?: string;
  needs_review?: boolean;
}

export async function fetchApplications(filters: ApplicationFilters = {}): Promise<Application[]> {
  const params = new URLSearchParams();
  if (filters.site) params.set("site", filters.site);
  if (filters.status) params.set("status", filters.status);
  if (filters.needs_review !== undefined) params.set("needs_review", String(filters.needs_review));

  const response = await fetch(`${API_BASE_URL}/api/applications?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch applications: ${response.status}`);
  }
  return response.json();
}

export async function updateApplicationReviewed(id: number, reviewed: boolean): Promise<Application> {
  const response = await fetch(`${API_BASE_URL}/api/applications/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewed }),
  });
  if (!response.ok) {
    throw new Error(`Failed to update application: ${response.status}`);
  }
  return response.json();
}

export async function triggerRun(sites: string[], searchTerm: string): Promise<{ task_arn: string }> {
  const response = await fetch(`${API_BASE_URL}/api/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sites: sites.length > 0 ? sites : undefined,
      search_term: searchTerm || undefined,
    }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || `Failed to trigger run: ${response.status}`);
  }
  return response.json();
}
