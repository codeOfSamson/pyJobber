import { useState } from "react";
import { Button, Checkbox, TextInput, Window, WindowContent, WindowHeader } from "react95";
import { triggerRun } from "../api";

const ALL_SITES = ["cakeresume", "104", "linkedin"];

export function RunNowWindow() {
  const [selectedSites, setSelectedSites] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggleSite = (site: string) => {
    setSelectedSites((prev) =>
      prev.includes(site) ? prev.filter((s) => s !== site) : [...prev, site]
    );
  };

  const confirmAndRun = async () => {
    setShowConfirm(false);
    setError(null);
    setResult(null);
    try {
      const { task_arn } = await triggerRun(selectedSites, searchTerm);
      setResult(task_arn);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <Window className="w-full">
      <WindowHeader>Run Now</WindowHeader>
      <WindowContent>
        <div className="flex gap-4 mb-4">
          {ALL_SITES.map((site) => (
            <Checkbox
              key={site}
              label={site}
              checked={selectedSites.includes(site)}
              onChange={() => toggleSite(site)}
            />
          ))}
        </div>
        <TextInput
          placeholder="Search term override (optional)"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          fullWidth
        />
        <Button className="mt-4" onClick={() => setShowConfirm(true)}>
          Run Now
        </Button>

        {result && <p className="mt-4">Task started: {result}</p>}
        {error && <p className="mt-4">Failed to start run: {error}</p>}
      </WindowContent>

      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Window>
            <WindowHeader>Confirm</WindowHeader>
            <WindowContent>
              <p>
                This submits real applications to real employers on{" "}
                {selectedSites.length > 0 ? selectedSites.join(", ") : "the default configured sites"}.
              </p>
              <div className="flex gap-4 mt-4">
                <Button onClick={confirmAndRun}>Yes, run it</Button>
                <Button onClick={() => setShowConfirm(false)}>Cancel</Button>
              </div>
            </WindowContent>
          </Window>
        </div>
      )}
    </Window>
  );
}
