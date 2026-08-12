import { useEffect, useState } from "react";
import { Checkbox, Select, Window, WindowContent, WindowHeader } from "react95";
import {
  type Application,
  fetchApplications,
  updateApplicationReviewed,
} from "../api";

const SITE_OPTIONS = [
  { value: "", label: "All sites" },
  { value: "cakeresume", label: "CakeResume" },
  { value: "104", label: "104.com.tw" },
  { value: "linkedin", label: "LinkedIn" },
];

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "applied", label: "Applied" },
  { value: "failed", label: "Failed" },
  { value: "skipped", label: "Skipped" },
];

export function ApplicationsWindow() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [site, setSite] = useState("");
  const [status, setStatus] = useState("");
  const [onlyNeedsReview, setOnlyNeedsReview] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    fetchApplications({
      site: site || undefined,
      status: status || undefined,
      needs_review: onlyNeedsReview ? true : undefined,
    })
      .then(setApplications)
      .catch((e) => setError(e.message));
  };

  useEffect(load, [site, status, onlyNeedsReview]);

  const toggleReviewed = async (app: Application) => {
    const updated = await updateApplicationReviewed(app.id, !app.reviewed);
    setApplications((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
  };

  return (
    <Window className="w-full">
      <WindowHeader>Applications</WindowHeader>
      <WindowContent>
        {error && <p>API unreachable — is `uvicorn` running? ({error})</p>}

        <div className="flex items-center gap-4 mb-4">
          <Select
            options={SITE_OPTIONS}
            value={site}
            onChange={(option) => setSite(option.value as string)}
            width={180}
          />
          <Select
            options={STATUS_OPTIONS}
            value={status}
            onChange={(option) => setStatus(option.value as string)}
            width={180}
          />
          <Checkbox
            checked={onlyNeedsReview}
            onChange={(e) => setOnlyNeedsReview(e.target.checked)}
            label="Needs review only"
          />
        </div>

        <table className="w-full text-left text-sm">
          <thead>
            <tr>
              <th>Site</th>
              <th>Status</th>
              <th>URL</th>
              <th>Reviewed</th>
            </tr>
          </thead>
          <tbody>
            {applications.map((app) => (
              <tr key={app.id}>
                <td>{app.site}</td>
                <td>{app.status}</td>
                <td className="truncate max-w-xs">
                  <a href={app.url} target="_blank" rel="noreferrer">
                    {app.url}
                  </a>
                </td>
                <td>
                  <Checkbox checked={app.reviewed} onChange={() => toggleReviewed(app)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </WindowContent>
    </Window>
  );
}
