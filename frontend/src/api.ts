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
