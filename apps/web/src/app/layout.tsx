import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "ShopFilter Eval",
    template: "%s · ShopFilter Eval",
  },
  description: "Evidence-based quality engineering for e-commerce search.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
