import { ThemeProvider, createGlobalStyle } from "styled-components";
import original from "react95/dist/themes/original";
import { styleReset } from "react95";
import { StatsWindow } from "./windows/StatsWindow";
import { ApplicationsWindow } from "./windows/ApplicationsWindow";
import { RunNowWindow } from "./windows/RunNowWindow";

const GlobalStyles = createGlobalStyle`
  ${styleReset}
`;

function App() {
  return (
    <ThemeProvider theme={original}>
      <GlobalStyles />
      <div className="min-h-screen bg-teal-700 p-8 flex flex-col gap-6">
        <h1
          className="text-center text-4xl font-bold uppercase tracking-widest text-gray-200"
          style={{
            textShadow:
              "1px 1px 0 #399aab, 2px 2px 0 #808080, 3px 3px 0 #404040",
          }}
        >
          Job Scraper and Tracker
        </h1>
        <StatsWindow />
        <div className="flex flex-1 gap-6">
          <div className="flex-1">
            <ApplicationsWindow />
          </div>
          <div className="flex-1">
            <RunNowWindow />
          </div>
        </div>
      </div>
    </ThemeProvider>
  );
}

export default App;
