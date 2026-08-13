import { useEffect, useState } from "react";
import { Window, WindowHeader, WindowContent } from "react95";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchStats, type RunStat } from "../api";

export function StatsWindow() {
  const [stats, setStats] = useState<RunStat[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <Window className="w-full">
      <WindowHeader>Applications Over Time</WindowHeader>
      <WindowContent>
        {error && <p>API unreachable — is `uvicorn` running? ({error})</p>}
        {!error && (
          <div style={{ width: "100%", height: 300 }}>
            <ResponsiveContainer>
              <LineChart data={stats}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="run_date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="total_applied"
                  stroke="#2e7d32"
                  name="Applied"
                />
                <Line
                  type="monotone"
                  dataKey="total_failed"
                  stroke="#c62828"
                  name="Failed"
                />
                <Line
                  type="monotone"
                  dataKey="total_skipped"
                  stroke="#f9a825"
                  name="Skipped"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </WindowContent>
    </Window>
  );
}
