import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Drug Screen Designer",
  description: "Plate layout → worklist → Opentrons Flex",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
