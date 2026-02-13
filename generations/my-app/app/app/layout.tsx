import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { CopilotProvider } from "@/lib/copilot-provider";

export const metadata: Metadata = {
  title: "AI Coding Dashboard",
  description: "Generative UI with CopilotKit and A2UI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body>
        <CopilotProvider>
          {children}
          <Toaster />
        </CopilotProvider>
      </body>
    </html>
  );
}
