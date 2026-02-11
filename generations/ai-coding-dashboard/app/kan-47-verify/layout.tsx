import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "../globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "KAN-47 Verification | AI Coding Dashboard",
  description: "Verification page for KAN-47 project initialization",
};

/**
 * Simple layout for KAN-47 verification page
 * This bypasses the CopilotKit provider to show the base Next.js + Tailwind setup
 */
export default function KAN47Layout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
