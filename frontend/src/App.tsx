import { ThemeProvider, createGlobalStyle } from "styled-components";
import original from "react95/dist/themes/original";
import { Window, WindowHeader, WindowContent, styleReset } from "react95";

const GlobalStyles = createGlobalStyle`
  ${styleReset}
`;

function App() {
  return (
    <ThemeProvider theme={original}>
      <GlobalStyles />
      <div className="min-h-screen bg-teal-700 flex items-center justify-center p-8">
        <Window>
          <WindowHeader>Autojobber Dashboard</WindowHeader>
          <WindowContent>Scaffold OK.</WindowContent>
        </Window>
      </div>
    </ThemeProvider>
  );
}

export default App;
