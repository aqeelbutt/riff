import "./globals.css";
import { TopBar } from "@/components/TopBar";
import { PlayerProvider } from "@/features/player/PlayerProvider";

export const metadata = { title: "Riff", description: "AI music studio on your own Mac" };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap"
        />
      </head>
      <body className="min-h-screen"><PlayerProvider><TopBar />{children}</PlayerProvider></body>
    </html>
  );
}
