import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stance Tracker",
  description: "Track candidate positions on issues over time using AI-powered memory",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
