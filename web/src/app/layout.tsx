import type { Metadata } from "next";
import "./globals.css";
import { RuntimeProvider } from "@/lib/context/runtime-context";

export const metadata: Metadata = {
  title: "VoiceSaju",
  description: "AI-powered Saju reading and daily tarot service.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css"
        />
      </head>
      <body className="font-sans antialiased">
        <RuntimeProvider>{children}</RuntimeProvider>
      </body>
    </html>
  );
}
