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
        <StatsWindow />
        <ApplicationsWindow />
        <RunNowWindow />
      </div>
    </ThemeProvider>
  );
}

export default App;
